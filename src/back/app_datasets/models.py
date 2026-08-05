# src/back/app_datasets/models.py
"""
ORM-модели приложения app_datasets.
Единственная модель — DataSetsVerified (таблица dim_data_sets_verified).
"""
from datetime import datetime
from typing import Optional, Union

from sqlalchemy import String, Integer, Boolean, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base

SCHEMA_NAME = "app_datasets"
TABLE_ARGS = {"schema": SCHEMA_NAME}


class DataSetsVerified(Base):
    """
    Таблица app_datasets.dim_data_sets_verified.
    PK — hash_sum (SHA-256), без autoincrement.
    """

    __tablename__ = "dim_data_sets_verified"
    __table_args__ = TABLE_ARGS

    # Переопределяем id из Base: nullable, НЕ PK
    id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # PK — hash_sum
    hash_sum: Mapped[str] = mapped_column(
        String(64), primary_key=True, autoincrement=False
    )

    # Убираем стандартные created_at / updated_at из Base
    created_at = None
    updated_at = None

    date_created: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=True,
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    period: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    link: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    validation: Mapped[Optional[Union[dict, list]]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<DataSetsVerified(hash_sum='{self.hash_sum[:16]}...', name='{self.name}')>"
