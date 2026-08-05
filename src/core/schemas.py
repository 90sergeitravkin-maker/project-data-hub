# src/core/schemas.py
"""
Базовые Pydantic-схемы для всех приложений.
"""

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """
    Базовая схема с общими настройками:
    - from_attributes = True (бывшее orm_mode)
    - extra = ignore (игнорируем лишние поля)
    """
    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore"
    )
