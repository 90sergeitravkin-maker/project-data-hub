# src/back/app_ecomru/schemas.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


class ColumnDefinition(BaseModel):
    """Описание колонки с типом данных."""
    name: str = Field(..., description="Имя колонки")
    data_type: str = Field(..., description="Тип данных: String, Date, Datetime, Integer и т.д.")

    @field_validator('data_type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {'String', 'Integer', 'Float', 'Date', 'Datetime', 'Boolean', 'JSON'}
        # Парсим типы вида Datetime("Europe/Moscow")
        base_type = v.split('(')[0] if '(' in v else v
        if base_type not in allowed:
            raise ValueError(f"Недопустимый тип: {base_type}. Разрешено: {allowed}")
        return v


class SourceConfig(BaseModel):
    """Конфигурация источника данных COMTRADE."""
    name: str = Field(..., min_length=3, max_length=100, description="Уникальное имя источника")
    maxDate: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$', description="Максимальная дата данных")
    description: str = Field(..., max_length=500)
    quantity: int = Field(..., ge=0, description="Ожидаемое количество записей")
    schedule: str = Field(..., description="Cron-расписание обновления")
    entityLink: str = Field(..., description="URL эндпоинта API")
    column: List[ColumnDefinition] = Field(..., min_length=1)
    uniqueTogether: List[str] = Field(default_factory=list, description="Поля для уникальности")

    # Дополнительные поля для внутренней обработки
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {'from_attributes': True, 'extra': 'ignore'}