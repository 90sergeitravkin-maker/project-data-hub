# src/back/app_monitor/models.py
"""Модели мониторинга. Схема app_monitor, управление — Alembic."""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, BigInteger, DateTime, Float, Text, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base

SCHEMA_NAME = "app_monitor"
TABLE_ARGS = {"schema": SCHEMA_NAME}


class MemorySnapshot(Base):
    __tablename__ = "memory_snapshots"
    __table_args__ = (
        Index("idx_memory_snapshots_app_ts", "app_name", "captured_at"),
        Index("idx_memory_snapshots_ts", "captured_at"),
        TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    app_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    rss_mb: Mapped[float] = mapped_column(Float, nullable=False)
    vms_mb: Mapped[float] = mapped_column(Float, nullable=False)
    shared_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    percent: Mapped[float] = mapped_column(Float, nullable=False)
    requests_count: Mapped[int] = mapped_column(Integer, default=0)
    peak_rss_mb: Mapped[float] = mapped_column(Float, default=0.0)


class RequestMemoryStat(Base):
    __tablename__ = "request_memory_stats"
    __table_args__ = (
        Index("idx_req_mem_app_ts", "app_name", "captured_at"),
        Index("idx_req_mem_heavy", "rss_delta_mb"),
        TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    app_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    rss_before_mb: Mapped[float] = mapped_column(Float, nullable=False)
    rss_after_mb: Mapped[float] = mapped_column(Float, nullable=False)
    rss_delta_mb: Mapped[float] = mapped_column(Float, nullable=False)
    peak_during_mb: Mapped[float] = mapped_column(Float, nullable=False)


class MemoryAlert(Base):
    __tablename__ = "memory_alerts"
    __table_args__ = (
        Index("idx_mem_alerts_ts", "fired_at"),
        Index("idx_mem_alerts_app_level", "app_name", "level"),
        TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    app_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    rss_mb: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_mb: Mapped[float] = mapped_column(Float, nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
