# src/back/app_mail/models.py
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer, Text, func, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base

SCHEMA_NAME = "app_mail"
TABLE_ARGS = {"schema": SCHEMA_NAME}


class MailTask(Base):
    """Основная таблица для трекинга задач отправки писем."""
    __tablename__ = "mail_tasks"
    __table_args__ = TABLE_ARGS
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, unique=True, nullable=False, index=True, default=uuid.uuid4
    )
    to_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<MailTask(id={self.id}, task_id='{self.task_id}', status='{self.status}')>"
