# src/front/web_monitor/api.py
"""
Web-интерфейс мониторинга ресурсов.
- GET /              → HTML-страница (шаблон)
- GET /api/*         → прокси к backend app_monitor
"""
from typing import Optional
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from src.front.web_monitor.config import templates, TAG_NAME
from src.front.web_monitor.services import WebMonitorService

router = APIRouter(tags=[TAG_NAME])


# ==================== HTML-страница ====================
@router.get("/", response_class=HTMLResponse, summary="Главная страница монитора")
async def monitor_index(request: Request):
    """Отображает HTML-страницу мониторинга ресурсов."""
    return templates.TemplateResponse(
        name="web_monitor/index.html",
        request=request,
        context={"page_title": "Resource Monitor"},
    )


# ==================== Прокси к backend app_monitor ====================
@router.get("/api/report", summary="Сводный отчёт по RAM (live)")
async def api_report():
    return await WebMonitorService.get_report()


@router.get("/api/snapshots", summary="История снимков памяти")
async def api_snapshots(
        app_name: Optional[str] = None,
        minutes: int = 60,
        limit: int = 200,
):
    return await WebMonitorService.get_snapshots(
        app_name=app_name, minutes=minutes, limit=limit
    )


@router.get("/api/heavy-requests", summary="Топ тяжёлых запросов")
async def api_heavy_requests(minutes: int = 60, top_n: int = 10):
    return await WebMonitorService.get_heavy_requests(minutes=minutes, top_n=top_n)


@router.get("/api/alerts", summary="Журнал алертов")
async def api_alerts(limit: int = 30):
    return await WebMonitorService.get_alerts(limit=limit)


@router.get("/api/disk-usage")
async def api_disk_usage():
    return await WebMonitorService.get_disk_usage()

