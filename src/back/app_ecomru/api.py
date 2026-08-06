# src/back/app_ecomru/api.py
"""API-слой приложения ECOMRU. Бизнес-логика отсутствует – только вызовы сервисов."""
import asyncio

from typing import Dict, Any
from fastapi import APIRouter, HTTPException

from src.back.app_ecomru.site import SiteApi
from src.back.app_ecomru.config import TAG_NAME
from src.back.app_ecomru.check_data.services import process_data_folder as process_data_folder_sync
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
    summary="Обработать папку: разбить файлы по столбцу",
    response_model=Dict[str, Any]
)
async def process_folder_endpoint(
        folder_path: str,
        split_column: str = "dataset_checksum"
) -> Dict[str, Any]:
    """
    Обработка папки с данными: разбиение файлов по указанному столбцу.

    Args:
        folder_path: Относительный путь внутри DATA_FILE_RAW
        split_column: Столбец для разбиения (по умолчанию dataset_checksum)

    Returns:
        Результат обработки: статус, статистика, информация о разбиении.
    """
    try:
        # Вызов синхронной функции в отдельном потоке, чтобы не блокировать event loop

        result = await asyncio.to_thread(process_data_folder_sync, folder_path, split_column)
        return result
    except Exception as e:
        logger.error(f"[ECOMRU] Ошибка при обработке папки {folder_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")