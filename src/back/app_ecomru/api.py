# src/back/app_ecomru/api.py
"""API-слой приложения ECOMRU. Бизнес-логика отсутствует – только вызовы сервисов."""
import asyncio
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.back.app_ecomru.site import SiteApi
from src.back.app_ecomru.config import TAG_NAME
from src.back.app_ecomru.split_data.services import process_data_folder as process_data_folder_sync
from src.core.logger import logger

router = APIRouter(tags=[TAG_NAME])


@router.get(
    "/entities",
    summary="Получить список сущностей"
)
async def entities_endpoint():
    """Получение списка сущностей (вызов сервиса)."""
    return SiteApi().entities_v1()


@router.post(
    "/process-folder",
    summary="Обработать папку: разбить файлы по столбцу(ам)",
    response_model=Dict[str, Any]
)
async def process_folder_endpoint(
        folder_path: str,
        split_columns: Optional[List[str]] = Query(
            None,
            description="Список столбцов для разбиения. "
                        "Если не указан — определяется из _fields_config.json по entity."
        ),
) -> Dict[str, Any]:
    """
    Обработка папки с данными: разбиение файлов по указанным столбцам.

    Args:
        folder_path: Относительный путь внутри DATA_FILE_RAW
        split_columns: Список столбцов для разбиения (опционально).
            Если не указан — читается из _fields_config.json (hot-reload).

    Returns:
        Результат обработки: статус, статистика, информация о разбиении.
    """
    try:
        # Вызов синхронной функции в отдельном потоке, чтобы не блокировать event loop
        result = await asyncio.to_thread(
            process_data_folder_sync, folder_path, split_columns
        )
        return result
    except Exception as e:
        logger.error(f"[ECOMRU] Ошибка при обработке папки {folder_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")
