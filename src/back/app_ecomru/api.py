# src/back/app_ecomru/api.py
"""API-слой приложения ECOMRU. Бизнес-логика отсутствует – только вызовы сервисов."""
from fastapi import APIRouter

from src.back.app_ecomru.site import SiteApi
from src.back.app_ecomru.config import TAG_NAME

router = APIRouter(tags=[TAG_NAME])


@router.get(
    "/entities",
    summary="Получить список сущностей"
)
async def entities_endpoint():
    """Получение списка сущностей (вызов сервиса)."""
    return SiteApi().entities_v1()
