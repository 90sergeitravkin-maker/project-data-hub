# src/front/web_architecture/api.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.front.web_architecture.services import ArchitectureCollector
from src.front.web_architecture.config import TAG_NAME, templates

router = APIRouter(tags=[TAG_NAME])


@router.get(
    "/", response_class=HTMLResponse
)
async def architecture_page(request: Request):
    return templates.TemplateResponse(request=request, name="web_architecture/index.html", context={})


@router.get(
    "/api/architecture"
)
async def get_architecture(request: Request):
    """Возвращает JSON-структуру приложения (app берётся из request, без циклического импорта)."""
    return ArchitectureCollector.get_app_info(request.app)
