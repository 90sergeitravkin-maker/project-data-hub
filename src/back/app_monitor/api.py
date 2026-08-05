# src/back/app_monitor/api.py
"""
Ручки мониторинга. УБРАНА аутентификация для внутреннего использования.
"""
from fastapi import APIRouter, Query
from datetime import datetime, timezone
from src.back.app_monitor.config import TAG_NAME, DISK_PATHS
from src.back.app_monitor.services import MemoryMonitorService
from src.back.app_monitor.schemas import (
    AppsMemoryReport, SnapshotRecord, HeavyRequestRecord,
    AlertRecord, MemoryDiagnostics, SnapshotQuery, HeavyRequestsQuery, DiskUsageResponse,
)

router = APIRouter(tags=[TAG_NAME])


@router.get(
    "/report",
    response_model=AppsMemoryReport,
    summary="Сводный отчёт по RAM всех приложений (live)",
)
async def get_report():
    return await MemoryMonitorService.get_apps_report()


@router.get(
    "/snapshots",
    response_model=list[SnapshotRecord],
    summary="История снимков памяти",
)
async def get_snapshots(q: SnapshotQuery = Query()):
    return await MemoryMonitorService.get_snapshots(q.app_name, q.minutes, q.limit)


@router.get(
    "/heavy-requests",
    response_model=list[HeavyRequestRecord],
    summary="Топ-N самых 'тяжёлых' запросов по приросту RAM",
)
async def get_heavy_requests(q: HeavyRequestsQuery = Query()):
    return await MemoryMonitorService.get_heavy_requests(q.minutes, q.top_n, q.min_delta_mb)


@router.get(
    "/alerts",
    response_model=list[AlertRecord],
    summary="Журнал алертов по превышению порогов",
)
async def get_alerts(limit: int = Query(50, ge=1, le=500)):
    return await MemoryMonitorService.get_alerts(limit)


@router.get(
    "/diagnostics",
    response_model=MemoryDiagnostics,
    summary="Полная диагностика: процесс + tracemalloc + приложения",
)
async def get_diagnostics():
    return await MemoryMonitorService.get_full_diagnostics()


@router.get(
    "/health",
    summary="Health-check монитора",
)
async def health():
    return {"status": "ok", "service": "app_monitor"}


@router.get("/disk-usage",
            response_model=DiskUsageResponse,
            summary="Информация о дисковом пространстве для заданных папок")
async def get_disk_usage():
    items = MemoryMonitorService.get_disk_usage(DISK_PATHS)
    return DiskUsageResponse(
        paths=items,
        captured_at=datetime.now(timezone.utc)
    )
