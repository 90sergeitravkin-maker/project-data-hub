# src/back/app_text_dup_check/models.py
from sqlalchemy import Text, String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base

SCHEMA_NAME = "app_text_dup_check"
TABLE_ARGS = {"schema": SCHEMA_NAME}


class TextEntry(Base):
    __tablename__ = "texts"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, index=True)
