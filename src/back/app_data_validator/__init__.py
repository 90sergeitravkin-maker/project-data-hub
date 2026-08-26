# src/back/app_data_validator/__init__.py
"""
Приложение для валидации файлов данных (CSV, Parquet, XLSX, XLS).
"""
from .api import router
from .config import TAG_NAME, API_PREFIX_V1, openapi_tags

__all__ = [
    'router',
    'TAG_NAME',
    'API_PREFIX_V1',
    'openapi_tags',
]
