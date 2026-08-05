# src/front/web_data_registry/api.py
"""
Простой веб-интерфейс для личного кабинета.
Все веб-страницы помечены тегом "WEB LK" для фильтрации в /docs-web
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from src.front.web_data_registry.config import templates, TAG_NAME

router = APIRouter(tags=[TAG_NAME])


@router.get("/login", response_class=HTMLResponse, tags=[TAG_NAME])
async def login_page(request: Request, error: str = None, success: str = None):
    return templates.TemplateResponse(
        name="login.html",
        request=request,
        context={"error": error, "success": success, "form_data": {}, "csrf_token": ""}
    )
