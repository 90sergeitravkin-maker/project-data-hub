# src/back/app_monitor/middleware.py
"""
Middleware для per-request трекинга потребления RAM по приложениям.
Определяет app_name по префиксу пути (из openapi_tags / router).
"""
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from src.core.logger import logger
from src.back.app_monitor.services import MemoryMonitorService

# Маппинг префиксов → app_name (заполняется при старте)
_PREFIX_TO_APP: dict[str, str] = {}


def register_app_prefix(prefix: str, app_name: str) -> None:
    """Регистрирует префикс для маппинга в мониторинге."""
    _PREFIX_TO_APP[prefix.rstrip("/")] = app_name


def _resolve_app_name(path: str) -> str:
    """Определяет app_name по пути запроса."""
    # Ищем самый длинный подходящий префикс
    best_match = ""
    best_app = "unknown"
    for prefix, app_name in _PREFIX_TO_APP.items():
        if path.startswith(prefix) and len(prefix) > len(best_match):
            best_match = prefix
            best_app = app_name
    return best_app


class MemoryTrackingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Пропускаем системные эндпоинты и статику
        path = request.url.path
        if path.startswith(("/static", "/docs", "/redoc", "/openapi.json", "/api/v1/app_monitor")):
            return await call_next(request)

        app_name = _resolve_app_name(path)
        start_ts = time.perf_counter()
        rss_before = await MemoryMonitorService.on_request_start(app_name)

        try:
            response = await call_next(request)
        except Exception as e:
            duration_ms = (time.perf_counter() - start_ts) * 1000
            await MemoryMonitorService.on_request_end(
                app_name=app_name,
                method=request.method,
                path=path,
                status_code=500,
                duration_ms=duration_ms,
                rss_before=rss_before,
                save_to_db=True,
            )
            raise

        duration_ms = (time.perf_counter() - start_ts) * 1000
        await MemoryMonitorService.on_request_end(
            app_name=app_name,
            method=request.method,
            path=path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            rss_before=rss_before,
            save_to_db=True,
        )
        return response