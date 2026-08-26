#  src/back/app_data_registry/schemas.py
"""
Pydantic схемы для валидации запросов/ответов API.
Изолированы от ORM-моделей.
"""

from typing import Any, Optional, List, Dict
from pydantic import BaseModel, Field
from pydantic import field_validator


class BaseSchema(BaseModel):
    """Базовая схема с настройками."""
    model_config = {'from_attributes': True, 'extra': 'ignore'}


class FieldMetadata(BaseModel):
    """Метаданные поля: тип + допустимость NULL."""
    type: str = Field(..., description="Нормализованный тип данных")
    null: bool = Field(..., description="Допускает ли поле значения NULL")


class ExtractSchemaRequest(BaseSchema):
    file_path: str = Field(..., description="Путь к файлу относительно DATA_ROOT_DIR")

    @field_validator('file_path')
    @classmethod
    def validate_no_traversal(cls, v: str) -> str:
        if '..' in v or v.startswith('/'):
            raise ValueError('Путь не должен содержать ".." или начинаться с "/"')
        return v.strip()


class ExtractSchemaResponse(BaseSchema):
    success: bool
    message: str
    schema_: Dict[str, FieldMetadata] = Field(
        default_factory=dict,
        description="Схема файла",
        alias="schema",
        serialization_alias="schema"
    )
    file_path: str = Field(..., description="Возвращается точно как в запросе")
    file_type: str
    error: Optional[str] = Field(None)

    model_config = {
        'from_attributes': True,
        'extra': 'ignore',
        'protected_namespaces': (),
        'populate_by_name': True
    }


class CheckDataRequest(BaseSchema):
    folders: Optional[List[str]] = Field(None, description="Список папок для проверки")


class CheckDataResponse(BaseSchema):
    """Ответ проверки данных."""
    success: bool
    message: str
    missing: List[str] = Field(default_factory=list, description="Отсутствующие папки")
    empty: List[str] = Field(default_factory=list, description="Пустые папки")

    # ← ИЗМЕНЕНО: теперь список словарей {папка: дата}
    found: List[Dict[str, Optional[str]]] = Field(
        default_factory=list,
        description="Найденные папки с датами: [{'папка': '2026-03-18'}, ...]"
    )
    total_checked: int = Field(0, description="Всего проверено папок")


class DirectoryContentResponse(BaseSchema):
    """Содержимое директории: папки и файлы с пагинацией."""
    success: bool
    path: str = Field(..., description="Текущий путь относительно DATA_ROOT_DIR")
    folders: List[str] = Field(default_factory=list, description="Вложенные папки")
    files: List[str] = Field(default_factory=list, description="Файлы в текущей папке")
    total: int = Field(0, description="Всего элементов в директории")
    page: int = Field(1, ge=1, description="Текущая страница")
    page_size: int = Field(50, ge=1, le=1000, description="Размер страницы")
    has_next: bool = Field(False, description="Есть ли следующая страница")
    has_prev: bool = Field(False, description="Есть ли предыдущая страница")
    excluded: int = Field(0, description="Исключённых системных папок")
    error: Optional[str] = Field(None)
    model_config = {'from_attributes': True, 'extra': 'ignore'}


class UploadFileRequest(BaseSchema):
    """Запрос на загрузку файла."""
    file_path: str = Field(
        ...,
        description="Целевой путь относительно DATA_ROOT_DIR",
        examples=["exports/2025-04-08/comtrade.json.parquet"]
    )
    overwrite: bool = Field(default=False, description="Разрешить перезапись")


class UploadFileResponse(BaseSchema):
    """Ответ после загрузки файла."""
    success: bool
    message: str
    file_path: str = Field(..., description="Полный сохранённый путь")
    file_size: int = Field(0, description="Размер файла в байтах")
    stored_in: str = Field(..., description="Где сохранён: 'minio' | 'local'")
    error: Optional[str] = Field(None)


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


class FilePreviewRow(BaseModel):
    """Одна строка данных файла."""
    data: Dict[str, Any]
    model_config = {'extra': 'allow'}


class FilePreviewResponse(BaseSchema):
    """Ответ с превью файла: данные + метаданные + пагинация."""
    success: bool
    message: str
    file_path: str
    file_type: str
    columns: List[str] = Field(default_factory=list)
    total_rows: int = 0
    rows: List[FilePreviewRow] = Field(default_factory=list)
    page: int = 1
    page_size: int = 50
    has_next: bool = False
    error: Optional[str] = Field(None)
    model_config = {'from_attributes': True, 'extra': 'ignore'}
