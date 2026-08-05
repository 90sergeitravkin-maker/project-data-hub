# src/back/app_file_manager/api.py
import mimetypes
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status, UploadFile, File, Form, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.background import BackgroundTask

from src.core.logger import logger
from src.back.app_file_manager.config import TAG_NAME, DATA_ROOT_DIR, APP_TOKEN
from src.back.app_file_manager.services import AppDataChecker
from src.back.app_file_manager.schemas import (
    CheckDataResponse, CheckDataRequest,
    FoldersResponse,
    ExtractSchemaResponse, ExtractSchemaRequest, FilePreviewResponse,
)

router = APIRouter(tags=[TAG_NAME])
security = HTTPBearer(auto_error=False)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    if not APP_TOKEN:
        raise HTTPException(status_code=503, detail="Авторизация не настроена")
    token = credentials.credentials if credentials else ""
    if token not in APP_TOKEN:
        raise HTTPException(status_code=401, detail="Неверный токен")
    return True

@router.get("/available-folders", response_model=FoldersResponse, summary="Получение содержимого директории")
async def get_available_folders(folder_path: Optional[str] = Query(None),
                                pattern: Optional[str] = Query(None),
                                page: int = Query(1, ge=1),
                                page_size: int = Query(50, ge=1, le=1000)) -> FoldersResponse:
    success, result = await AppDataChecker.get_available_folders(
        root_dir=DATA_ROOT_DIR, folder_path=folder_path, pattern=pattern, page=page, page_size=page_size
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={'error': result.get('error')})
    return FoldersResponse(success=success, **result)

@router.post("/check-data", response_model=CheckDataResponse)
async def check_data(request: Optional[CheckDataRequest] = None):
    folders = request.folders if request else None
    success, result = await AppDataChecker.check_comtrade_data(base_url=DATA_ROOT_DIR, folders=folders)
    missing, empty, found_base = result.get('missing', []), result.get('empty', []), result.get('found', [])
    dates_map = await AppDataChecker.get_max_dates_for_folders(found_base, DATA_ROOT_DIR)
    found_formatted = [{f: dates_map.get(f) for f in found_base}]
    parts = []
    if missing: parts.append(f"не найдено: {len(missing)}")
    if empty: parts.append(f"пустые: {len(empty)}")
    if found_base: parts.append(f"с файлами: {len(found_base)}")

    return CheckDataResponse(success=success, message=" | ".join(parts) or "Нет данных", missing=missing, empty=empty,
                             found=found_formatted, total_checked=len(folders or []))

@router.post("/extract-schema", response_model=ExtractSchemaResponse, summary="Получить схему данных файла")
async def extract_schema(request: ExtractSchemaRequest):
    success, result = await AppDataChecker.extract_file_schema(file_path=request.file_path)
    if not success:
        return ExtractSchemaResponse(success=False, message="Не удалось извлечь схему", schema={},
                                     file_path=request.file_path, file_type=result.get('file_type', 'unknown'),
                                     error=result.get('error'))

    return ExtractSchemaResponse(
        success=True, message=f"Схема извлечена: {result.get('field_count', 0)} полей",
        schema={k: {"type": v["type"], "null": v["null"]} for k, v in result.get("schema", {}).items()},
        file_path=request.file_path, file_type=result.get("file_type", "unknown"), error=None
    )

@router.get("/download-file", summary="Скачать файл по пути")
async def download_file(file_path: str = Query(...), as_attachment: bool = Query(True)):
    try:
        base = Path(DATA_ROOT_DIR).resolve()
        full_path = (base / file_path).resolve()
        try:
            full_path.relative_to(base)
        except ValueError:
            return JSONResponse(status_code=403, content={"error": "Доступ запрещён"})
        if not full_path.exists() or not full_path.is_file():
            return JSONResponse(status_code=404, content={"error": "Файл не найден"})

        content_type, _ = mimetypes.guess_type(full_path.name)

        async def log_download():
            # Используем новый DBManager асинхронно
            from src.database.manager import DBManager
            db = DBManager()
            try:
                await db.execute("app_file_manager",
                                 "INSERT INTO file_download_log (file_path, downloaded_at, client_info) VALUES ($1, NOW(), $2)",
                                 file_path, "api_request")
            except Exception as e:
                logger.warning(f"Не удалось записать лог скачивания: {e}")

        return FileResponse(path=full_path, filename=full_path.name if as_attachment else None,
                            media_type=content_type or "application/octet-stream",
                            background=BackgroundTask(log_download))
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/upload-file", summary="Загрузка файла в хранилище", status_code=status.HTTP_200_OK)
async def upload_file(file: UploadFile = File(...), file_path: str = Form(...), overwrite: bool = Form(False)):
    try:
        safe_name = (file.filename or "uploaded_file").replace("/", "_").replace("\\", "_")
        success, result = await AppDataChecker.upload_file_to_storage(file_path=f"{file_path.rstrip('/')}/{safe_name}",
                                                                      file_content=await file.read(),
                                                                      overwrite=overwrite)
        if not success: raise HTTPException(status_code=400, detail=result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/preview-file", response_model=FilePreviewResponse, summary="Просмотр содержимого файла с фильтрацией")
async def preview_file(
        request: Request,
        file_path: str = Query(...),
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=200)
):
    column_filters = {k: v for k, v in request.query_params.items()
                      if k not in ("file_path", "page", "page_size") and v}

    success, result = await AppDataChecker.preview_file_content(
        file_path=file_path, base_dir=DATA_ROOT_DIR, page=page, page_size=page_size, column_filters=column_filters
    )

    if not success:
        return FilePreviewResponse(success=False, message="Ошибка чтения файла", file_path=file_path,
                                   file_type="unknown", error=result.get('error'))

    return FilePreviewResponse(
        success=True, message=result.get('message', 'OK'), file_path=file_path,
        file_type=result.get('file_type', 'unknown'), columns=result.get('columns', []),
        total_rows=result.get('total_rows', 0), rows=result.get('rows', []),
        page=result.get('page', 1), page_size=result.get('page_size', 50),
        has_next=result.get('has_next', False)
    )