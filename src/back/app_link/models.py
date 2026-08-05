# src/back/app_link/models.py
"""ORM-модель app_link.links (заменяет raw SQL из Link.init_table)."""
from datetime import datetime

from sqlalchemy import String, Text, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base

SCHEMA_NAME = "app_link"
TABLE_ARGS = {"schema": SCHEMA_NAME}


class Link(Base):
    __tablename__ = "links"
    __table_args__ = (
        Index("idx_links_url_hash", "url_hash"),
        Index("idx_links_url_normalized", "url_normalized"),
        TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
