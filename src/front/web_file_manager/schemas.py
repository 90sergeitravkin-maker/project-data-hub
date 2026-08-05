#  src/back/app_data_registry/schemas.py
"""
Pydantic схемы для валидации запросов/ответов API.
Изолированы от ORM-моделей.
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class BaseSchema(BaseModel):
    """Базовая схема с настройками."""
    model_config = {'from_attributes': True, 'extra': 'ignore'}


class FoldersResponse(BaseSchema):
    """Универсальный ответ: содержимое директории с пагинацией."""
    success: bool
    folders: List[str] = Field(default_factory=list, description="Подпапки на текущей странице")
    files: List[str] = Field(default_factory=list, description="Файлы на текущей странице")
    total: int = Field(0, description="Всего элементов найдено")
    page: int = Field(1, ge=1, description="Текущая страница")
    page_size: int = Field(50, ge=1, le=1000, description="Размер страницы")
    has_next: bool = Field(False)
    has_prev: bool = Field(False)
    excluded: int = Field(0, description="Количество исключённых элементов")
    current_path: str = Field('', description="Запрошенный путь относительно DATA_ROOT_DIR")
    applied_pattern: Optional[str] = Field(None, description="Применённый regex-фильтр")
    error: Optional[str] = Field(None)
    model_config = {'from_attributes': True, 'extra': 'ignore'}
