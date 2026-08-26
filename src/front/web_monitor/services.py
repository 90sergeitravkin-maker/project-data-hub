# src/front/web_monitor/services.py
"""
Сервис для web интерфейса monitor.
Напрямую вызывает backend-методы app_monitor (без HTTP-запросов).
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from src.back.app_monitor.services import MemoryMonitorService
from src.back.app_monitor.config import DISK_PATHS


class WebMonitorService:
    """Сервис для работы с web интерфейсом монитора."""

    @classmethod
    async def get_report(cls) -> Dict[str, Any]:
        """Сводный отчёт по RAM всех приложений (live)."""
        try:
            report = await MemoryMonitorService.get_apps_report()
            return report.model_dump()
        except Exception as e:
            return {"error": str(e), "status_code": 500}

    @classmethod
    async def get_snapshots(
        cls,
        app_name: Optional[str] = None,
        minutes: int = 60,
        limit: int = 200,
    ) -> Dict[str, Any]:
        """История снимков памяти."""
        try:
            snapshots = await MemoryMonitorService.get_snapshots(
                app_name=app_name,
                minutes=minutes,
                limit=limit,
            )
            return {
                "snapshots": [s.model_dump() for s in snapshots],
                "status": "ok",
            }
        except Exception as e:
            return {"error": str(e), "status_code": 500}

    @classmethod
    async def get_heavy_requests(
        cls,
        minutes: int = 60,
        top_n: int = 10,
    ) -> Dict[str, Any]:
        """Топ тяжёлых запросов."""
        try:
            heavy = await MemoryMonitorService.get_heavy_requests(
                minutes=minutes,
                top_n=top_n,
                min_delta_mb=1.0,
            )
            return {
                "heavy_requests": [h.model_dump() for h in heavy],
                "status": "ok",
            }
        except Exception as e:
            return {"error": str(e), "status_code": 500}

    @classmethod
    async def get_alerts(cls, limit: int = 30) -> Dict[str, Any]:
        """Журнал алертов."""
        try:
            alerts = await MemoryMonitorService.get_alerts(limit=limit)
            return {
                "alerts": [a.model_dump() for a in alerts],
                "status": "ok",
            }
        except Exception as e:
            return {"error": str(e), "status_code": 500}

    @classmethod
    async def get_disk_usage(cls) -> Dict[str, Any]:
        """Получить информацию о дисковом пространстве."""
        try:
            items = MemoryMonitorService.get_disk_usage(DISK_PATHS)
            return {
                "paths": items,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {"error": str(e), "status_code": 500}