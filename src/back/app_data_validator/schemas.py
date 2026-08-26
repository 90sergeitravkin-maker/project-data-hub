# src/back/app_data_validator/schemas.py

from typing import Optional, List, Dict, Any
from pydantic import Field
from src.core.schemas import BaseSchema


class ValidationErrorItem(BaseSchema):
    """Агрегированная ошибка валидации."""
    category: str = Field(..., description="Тип ошибки")
    row_num: Optional[int] = Field(None, description="Номер строки (первое вхождение)")
    column_name: Optional[str] = Field(None, description="Имя колонки")
    value: Optional[str] = Field(None, description="Проблемное значение")
    error_text: Optional[str] = Field(None, description="Описание ошибки")
    count: Optional[int] = Field(None, description="Количество вхождений")
    file_name: Optional[str] = Field(None, description="Имя файла (заполняется при валидации папки)")


class ValidationResponse(BaseSchema):
    """Результат валидации."""
    file: str
    source: str
    total_rows: int
    status: str = Field(..., description="OK | FAIL")
    error_summary: Dict[str, int] = Field(default_factory=dict)
    errors: List[ValidationErrorItem] = Field(default_factory=list)
    files_processed: Optional[List[str]] = Field(None, description="Список обработанных файлов (если передана папка)")
    diagnostic: Optional[Dict[str, Any]] = Field(None, description="Диагностическая информация при ошибках")
