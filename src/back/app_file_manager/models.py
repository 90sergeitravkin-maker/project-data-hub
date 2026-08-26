# src/back/app_file_manager/models.py
"""
SQLAlchemy модели для app_file_manager.
Ранее таблицы создавались через raw SQL в services.py.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, BigInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base

SCHEMA_NAME = "app_file_manager"
TABLE_ARGS = {"schema": SCHEMA_NAME}


class FileDownloadLog(Base):
    """Лог скачиваний файлов через API."""
    __tablename__ = "file_download_log"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    client_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<FileDownloadLog(id={self.id}, path='{self.file_path[:50]}...')>"


class SchemaExtractionLog(Base):
    """Лог извлечений схем файлов."""
    __tablename__ = "schema_extraction_log"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    schema_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<SchemaExtractionLog(id={self.id}, path='{self.file_path[:50]}...')>"