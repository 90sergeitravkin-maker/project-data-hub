# src/front/web_monitor/schemas.py
"""Pydantic схемы для web интерфейса (если нужны)."""
from pydantic import BaseModel, Field


class MonitorPageConfig(BaseModel):
    """Конфигурация страницы монитора."""
    refresh_interval_sec: int = Field(default=30, ge=5, le=300)
    history_minutes: int = Field(default=60, ge=1, le=1440)
    top_n_heavy: int = Field(default=10, ge=1, le=100)
