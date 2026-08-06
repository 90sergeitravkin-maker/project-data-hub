# src/front/web_monitor/download.py
"""
Прокси-сервис для web интерфейса monitor.
Вызывает backend app_monitor без авторизации.
"""
import httpx
from typing import Optional, Dict, Any
from src.core.logger import logger

MONITOR_API_BASE = "http://127.0.0.1:8081/api/v1/app_monitor"


class WebMonitorService:
    """Сервис для работы с web интерфейсом монитора."""

    @staticmethod
    async def _get(endpoint: str, params: Optional[dict] = None) -> Dict[str, Any]:
        """Универсальный GET-запрос к backend app_monitor."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{MONITOR_API_BASE}/{endpoint}",
                    params=params or {},
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code if e.response else 500
            logger.error(f"[WEB_MONITOR] HTTP {status_code} при получении {endpoint}")
            return {"error": f"HTTP {status_code}", "status_code": status_code}
        except httpx.HTTPError as e:
            logger.error(f"[WEB_MONITOR] Ошибка {endpoint}: {e}")
            return {"error": str(e), "status_code": 500}
        except Exception as e:
            logger.error(f"[WEB_MONITOR] Неожиданная ошибка {endpoint}: {e}")
            return {"error": str(e), "status_code": 500}

    @classmethod
    async def get_report(cls) -> Dict[str, Any]:
        return await cls._get("report")

    @classmethod
    async def get_snapshots(
            cls,
            app_name: Optional[str] = None,
            minutes: int = 60,
            limit: int = 200,
    ) -> Dict[str, Any]:
        params = {"minutes": minutes, "limit": limit}
        if app_name:
            params["app_name"] = app_name
        return await cls._get("snapshots", params)

    @classmethod
    async def get_heavy_requests(cls, minutes: int = 60, top_n: int = 10) -> Dict[str, Any]:
        return await cls._get(
            "heavy-requests",
            {"minutes": minutes, "top_n": top_n, "min_delta_mb": 1.0},
        )

    @classmethod
    async def get_alerts(cls, limit: int = 30) -> Dict[str, Any]:
        return await cls._get("alerts", {"limit": limit})

    @classmethod
    async def get_disk_usage(cls) -> Dict[str, Any]:
        """Получить информацию о дисковом пространстве."""
        return await cls._get("disk-usage")
