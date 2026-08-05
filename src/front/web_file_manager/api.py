# src/front/web_file_manager/api.py
"""
Веб-интерфейс управления файлами: просмотр папок с пагинацией.
Поддержка переключения между корнями: EXT / RAW / TEMP.
"""
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, status, Query
from fastapi.responses import HTMLResponse

# === ВАЖНО: API_PREFIX_V1 берём из FRONTEND конфига, а не backend! ===
from src.core.logger import logger
from src.front.web_file_manager.config import API_PREFIX_V1, templates, TAG_NAME
from src.back.app_file_manager.config import AVAILABLE_ROOTS
from src.back.app_file_manager.services import AppDataChecker

router = APIRouter(tags=[TAG_NAME])


def _resolve_root(root_key: Optional[str]) -> tuple[str, dict]:
    """Безопасно выбирает корень по ключу. Возвращает (key, info)."""
    if root_key and root_key in AVAILABLE_ROOTS:
        return root_key, AVAILABLE_ROOTS[root_key]
    return "ext", AVAILABLE_ROOTS["ext"]


def _normalize_path(folder_path: Optional[str]) -> str:
    """Нормализует путь: убирает лишние слеши, приводит к единому формату."""
    if not folder_path:
        return ""
    clean = folder_path.replace("\\", "/").strip("/")
    parts = [p for p in clean.split("/") if p]
    return "/".join(parts)


def _parent_path(folder_path: str) -> str:
    """Возвращает родительский путь."""
    if not folder_path:
        return ""
    parts = folder_path.split("/")
    if len(parts) <= 1:
        return ""
    return "/".join(parts[:-1])


@router.get(
    "/test",
    response_class=HTMLResponse,
    summary="Тестовая страница файлов",
    tags=[TAG_NAME],
)
async def page_view(
        request: Request,
        root: Optional[str] = Query(None, description="Корень: ext|raw|temp"),
        folder_path: Optional[str] = Query(None, max_length=500),
        search: Optional[str] = Query(None, max_length=200, description="Поиск по имени файла/папки"),
        pattern: Optional[str] = Query(None, max_length=200),
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=1000),
) -> HTMLResponse:
    # === Если root не задан — показываем страницу выбора корня ===
    if root is None:
        logger.info("[WEB_FILE_MANAGER/TEST]11111111111111111111111111111111111111111111111 Запрос: выбор корня")
        return templates.TemplateResponse(
            name="web_file_manager/test.html",
            request=request,
            context={
                "mode": "select_root",
                "available_roots": AVAILABLE_ROOTS,
                "api_prefix": API_PREFIX_V1,
            },
        )

    # === Если root задан — показываем содержимое ===
    root_key, root_info = _resolve_root(root)
    root_dir = root_info["path"]
    normalized_path = _normalize_path(folder_path)

    display_path = normalized_path if normalized_path else "/"
    # Полный путь на диске
    full_path = root_dir / normalized_path if normalized_path else root_dir

    logger.info(
        f"[WEB_FILE_MANAGER/TEST] root={root_key}, path={display_path}, "
        f"full_path={full_path}, search={search!r}, pattern={pattern!r}, "
        f"page={page}, page_size={page_size}"
    )
    try:
        # === РЕЖИМ ПОИСКА ===
        if search and search.strip():
            success, result = await AppDataChecker.search_in_directory(
                root_dir=root_dir,
                folder_path=normalized_path or None,
                search_query=search.strip(),
                page=page,
                page_size=page_size,
            )

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result.get('error', 'Unknown error'),
                )

            # Пагинация для поиска
            total = result.get("total", 0)
            current_page = result.get("page", 1)
            current_page_size = result.get("page_size", 50)
            total_pages = max(1, (total + current_page_size - 1) // current_page_size)
            start_page = max(1, current_page - 2)
            end_page = min(total_pages, current_page + 2) + 1
            page_range = list(range(start_page, end_page))

            # Query-строка для пагинации (с search)
            qp = [f"root={root_key}", f"search={search.strip()}"]
            if normalized_path:
                qp.append(f"folder_path={normalized_path}")
            qp.append(f"page_size={current_page_size}")
            query_string = "&".join(qp)

            pagination_context = {
                "total_pages": total_pages,
                "current_page": current_page,
                "query_params": query_string,
                "page_range": page_range,
                "has_next": result.get("has_next", False),
                "has_prev": result.get("has_prev", False),
            }

            return templates.TemplateResponse(
                name="web_file_manager/test.html",
                request=request,
                context={
                    "mode": "search",
                    "folders": result.get("folders", []),
                    "files": result.get("files", []),
                    "total_items": total,
                    "pagination": pagination_context,
                    "current_path": normalized_path,
                    "search_query": search.strip(),
                    "search_base_path": result.get("search_base_path", ""),
                    "page_size": current_page_size,
                    "current_root": root_key,
                    "root_label": root_info["label"],
                    "root_path": str(root_dir),
                    "available_roots": AVAILABLE_ROOTS,
                    "csrf_token": "",
                    "api_prefix": API_PREFIX_V1,
                },
            )

        # === ОБЫЧНЫЙ РЕЖИМ НАВИГАЦИИ ===
        else:
            success, result = await AppDataChecker.get_available_folders(
                root_dir=root_dir,
                folder_path=normalized_path or None,
                pattern=pattern,
                page=page,
                page_size=page_size,
            )

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result.get('error', 'Unknown error'),
                )

            # Пагинация
            total = result.get("total", 0)
            current_page = result.get("page", 1)
            current_page_size = result.get("page_size", 50)
            total_pages = max(1, (total + current_page_size - 1) // current_page_size)
            start_page = max(1, current_page - 2)
            end_page = min(total_pages, current_page + 2) + 1
            page_range = list(range(start_page, end_page))

            # Хлебные крошки
            breadcrumb_parts = []
            if normalized_path:
                breadcrumb_parts = normalized_path.split("/")

            # Query-строка
            qp = [f"root={root_key}"]
            if normalized_path:
                qp.append(f"folder_path={normalized_path}")
            if pattern:
                qp.append(f"pattern={pattern}")
            qp.append(f"page_size={current_page_size}")
            query_string = "&".join(qp)

            pagination_context = {
                "total_pages": total_pages,
                "current_page": current_page,
                "query_params": query_string,
                "page_range": page_range,
                "has_next": result.get("has_next", False),
                "has_prev": result.get("has_prev", False),
            }

            return templates.TemplateResponse(
                name="web_file_manager/test.html",
                request=request,
                context={
                    "mode": "browse",
                    "folders": result.get("folders", []),
                    "files": result.get("files", []),
                    "total_items": total,
                    "pagination": pagination_context,
                    "current_path": normalized_path,
                    "parent_path": _parent_path(normalized_path),
                    "breadcrumb_parts": breadcrumb_parts,
                    "applied_pattern": pattern,
                    "page_size": current_page_size,
                    "current_root": root_key,
                    "root_label": root_info["label"],
                    "root_path": str(root_dir),
                    "available_roots": AVAILABLE_ROOTS,
                    "csrf_token": "",
                    "api_prefix": API_PREFIX_V1,
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[WEB_FILE_MANAGER/TEST] Критическая ошибка: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Ошибка загрузки данных"},
        )


@router.get(
    "/preview",
    response_class=HTMLResponse,
    summary="Просмотр содержимого файла",
    tags=[TAG_NAME],
)
async def preview_file_page(
        request: Request,
        root: Optional[str] = Query("ext", description="Корень: ext|raw|temp"),
        file_path: str = Query(...),
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=200),
) -> HTMLResponse:
    root_key, root_info = _resolve_root(root)
    root_dir = root_info["path"]

    normalized_file_path = _normalize_path(file_path)

    column_filters = {
        k: v for k, v in request.query_params.items()
        if k not in ("file_path", "page", "page_size", "root") and v
    }

    try:
        success, result = await AppDataChecker.preview_file_content(
            file_path=normalized_file_path,
            base_dir=root_dir,
            page=page,
            page_size=page_size,
            column_filters=column_filters,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get('error', 'Не удалось прочитать файл'),
            )

        total_rows = result.get("total_rows", 0)
        current_page = result.get("page", 1)
        current_page_size = result.get("page_size", 50)
        total_pages = max(1, (total_rows + current_page_size - 1) // current_page_size)
        start_page = max(1, current_page - 2)
        end_page = min(total_pages, current_page + 2) + 1
        page_range = list(range(start_page, end_page))

        qp = [f"root={root_key}", f"file_path={normalized_file_path}", f"page_size={current_page_size}"]
        for k, v in request.query_params.items():
            if k not in ("file_path", "page", "page_size", "root") and v:
                qp.append(f"{k}={v}")
        query_string = "&".join(qp)

        pagination_context = {
            "total_pages": total_pages,
            "current_page": current_page,
            "query_params": query_string,
            "page_range": page_range,
            "has_next": result.get("has_next", False),
            "has_prev": current_page > 1,
        }

        path_parts = normalized_file_path.replace('\\', '/').split('/')

        return templates.TemplateResponse(
            name="web_file_manager/preview.html",
            request=request,
            context={
                "file_path": normalized_file_path,
                "file_type": result.get("file_type", "unknown"),
                "total_rows": total_rows,
                "columns": result.get("columns", []),
                "rows": result.get("rows", []),
                "page": current_page,
                "page_size": current_page_size,
                "has_next": result.get("has_next", False),
                "has_prev": current_page > 1,
                "pagination": pagination_context,
                "breadcrumb_parts": path_parts,
                "current_root": root_key,
                "root_label": root_info["label"],
                "available_roots": AVAILABLE_ROOTS,
                "api_prefix": API_PREFIX_V1,  # ← /api/v1/web_file_manager
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[WEB_FILE_MANAGER/PREVIEW] Критическая ошибка: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Ошибка загрузки файла"},
        )
