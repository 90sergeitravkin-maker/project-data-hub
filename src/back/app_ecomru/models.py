# src/back/app_ecomru/models.py
import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    String, BigInteger, DateTime, Text, JSON,
    ForeignKey, Index, UniqueConstraint, func, Boolean,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base

SCHEMA_NAME = "app_ecomru"
TABLE_ARGS = {"schema": SCHEMA_NAME}


class NotificationLog(Base):
    """Лог отправленных отчётов."""

    __tablename__ = "notification_log"
    __table_args__ = (
        UniqueConstraint("entity", "period", "report_updated_at", "report_type",
                         name="uq_notification_entity_period"),
        Index("idx_notification_log_lookup", "entity", "period", "report_updated_at", "report_type"),
        TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(50), nullable=False)
    # Бизнес-поле из Kafka (строка), переименовано во избежание конфликта с аудит-полем
    report_updated_at: Mapped[str] = mapped_column(String(50), nullable=False)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, default="verification")
    recipient: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProcessingGroup(Base):
    __tablename__ = "processing_groups"
    __table_args__ = TABLE_ARGS

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    period: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Бывшее updated_at (строка из Kafka) — переименовано, чтобы не конфликтовать с аудит-полем
    source_updated_at: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    result_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    files: Mapped[List["GroupFile"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class GroupFile(Base):
    __tablename__ = "group_files"
    __table_args__ = (
        UniqueConstraint("group_id", "url", name="uq_group_file_url"),
        Index("idx_group_file_status", "status"),
        TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    group_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA_NAME}.processing_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    local_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    group: Mapped["ProcessingGroup"] = relationship(back_populates="files")


class DownloadedFile(Base):
    __tablename__ = "downloaded_files"
    __table_args__ = (
        UniqueConstraint("url", "dest_path", name="uq_downloaded_url_dest"),
        Index("idx_downloaded_status", "status"),
        TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dest_path: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    file_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
