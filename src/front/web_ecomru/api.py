# src/front/web_ecomru/api.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.back.app_ecomru.download.entities import get_entities_from_external
from src.front.web_ecomru.config import templates, TAG_NAME

router = APIRouter(tags=[TAG_NAME])


@router.get("/entities", response_class=HTMLResponse, summary="Страница сущностей", tags=[TAG_NAME])
async def entities_page(request: Request, error: str = None, success: str = None):
    """Отображает страницу управления сущностями ECOMRU."""
    # Получаем данные напрямую через бэкенд-сервис
    result = await get_entities_from_external()

    # Если есть ошибка – передаём её в шаблон
    if result.get("status") == "error":
        error = result.get("message", "Ошибка получения данных")
        data = []
    else:
        data = result.get("data", [])

    return templates.TemplateResponse(
        name="web_ecomru/entities.html",
        request=request,
        context={
            "error": error,
            "success": success,
            "data": data,
            "form_data": {},
            "csrf_token": "",
            "page_title": "Сущности ECOMRU"
        }
    )
