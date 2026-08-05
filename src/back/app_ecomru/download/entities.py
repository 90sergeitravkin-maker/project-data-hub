# src/back/app_ecomru/download/entities.py
"""Получение списка сущностей из внешнего API ECOMRU."""
import asyncio
from typing import Dict, Any
from src.core.logger import logger
from src.back.app_ecomru.site import SiteApi


async def get_entities_from_external() -> Dict[str, Any]:
    """
    Получает список сущностей из внешнего API.
    Возвращает {"status": "ok"/"error", "data": [...], "message": "..."}
    """
    try:
        api = SiteApi()
        # SiteApi использует синхронный requests, поэтому запускаем в отдельном потоке,
        # чтобы не блокировать event loop FastAPI
        entities = await asyncio.to_thread(api.entities_v1)

        return {
            "status": "ok",
            "data": entities,
            "message": f"Получено сущностей: {len(entities) if isinstance(entities, list) else 0}",
        }
    except ConnectionError as e:
        logger.error(f"[ENTITIES] Ошибка соединения: {e}")
        return {"status": "error", "data": [], "message": str(e)}
    except Exception as e:
        logger.error(f"[ENTITIES] Неожиданная ошибка: {e}", exc_info=True)
        return {"status": "error", "data": [], "message": f"Ошибка: {type(e).__name__}: {e}"}