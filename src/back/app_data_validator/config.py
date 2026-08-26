# src/back/app_data_validator/config.py
from pathlib import Path
from src.core.env_loader import get_env


APP_NAME = "app_data_validator"
TAG_NAME = "APP Data Validator"
API_PREFIX_V1 = "/api/v1/validator"

# Жестко задаем путь, так как данные лежат вне проекта
BASE_DATA_DIR = Path(get_env("APP_FAIL_MANAGER_RAW")).resolve()
openapi_tags = {
    "name": TAG_NAME,
    "description": "Валидация файлов данных (CSV, Parquet, XLSX, XLS).",
}