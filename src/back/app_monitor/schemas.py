# src/back/app_monitor/schemas.py
"""Pydantic-схемы для app_monitor."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")


# === Запросы ===
class SnapshotQuery(BaseSchema):
    app_name: Optional[str] = Field(None, description="Фильтр по приложению")
    minutes: int = Field(60, ge=1, le=1440, description="Глубина истории в минутах")
    limit: int = Field(100, ge=1, le=1000)


class HeavyRequestsQuery(BaseSchema):
    minutes: int = Field(60, ge=1, le=1440)
    top_n: int = Field(10, ge=1, le=100)
    min_delta_mb: float = Field(1.0, ge=0.0, description="Минимальный прирост RAM для включения в отчёт")


# === Ответы ===
class ProcessMemoryInfo(BaseSchema):
    """Текущее состояние процесса (всего FastAPI)."""
    rss_mb: float
    vms_mb: float
    shared_mb: Optional[float] = None
    percent: float
    threads: int
    cpu_percent: float
    uptime_sec: float


class AppMemoryStat(BaseSchema):
    """Статистика по одному приложению."""
    app_name: str
    current_rss_mb: float
    peak_rss_mb: float
    requests_count: int
    avg_delta_per_request_mb: float
    percent_of_total: float


class AppsMemoryReport(BaseSchema):
    """Сводный отчёт по всем приложениям."""
    captured_at: datetime
    process: ProcessMemoryInfo
    apps: List[AppMemoryStat]
    total_tracked_mb: float
    untracked_mb: float


class SnapshotRecord(BaseSchema):
    id: int
    captured_at: datetime
    app_name: str
    rss_mb: float
    vms_mb: float
    percent: float
    requests_count: int
    peak_rss_mb: float


class HeavyRequestRecord(BaseSchema):
    id: int
    captured_at: datetime
    app_name: str
    method: str
    path: str
    status_code: int
    duration_ms: float
    rss_delta_mb: float
    peak_during_mb: float


class AlertRecord(BaseSchema):
    id: int
    fired_at: datetime
    app_name: str
    level: str
    rss_mb: float
    threshold_mb: float
    message: Optional[str] = None


class TracemallocTop(BaseSchema):
    """Топ-N файлов по потреблению памяти (из tracemalloc)."""
    file: str
    line: int
    size_mb: float
    count: int


class MemoryDiagnostics(BaseSchema):
    """Полная диагностика: процесс + tracemalloc + топ приложений."""
    process: ProcessMemoryInfo
    tracemalloc_enabled: bool
    tracemalloc_total_mb: float
    tracemalloc_top: List[TracemallocTop]
    apps: List[AppMemoryStat]


class DiskUsageItem(BaseSchema):
    """Информация о дисковом пространстве для одного пути."""
    path: str
    total_gb: float
    used_gb: float
    free_gb: float
    percent: float


class DiskUsageResponse(BaseSchema):
    """Ответ с данными по нескольким путям."""
    paths: List[DiskUsageItem]
    captured_at: datetime
