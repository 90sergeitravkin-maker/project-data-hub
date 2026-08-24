# src/back/app_data_validator/config.py
from pathlib import Path

APP_NAME = "app_data_validator"
TAG_NAME = "APP Data Validator"
API_PREFIX_V1 = "/api/v1/validator"

# Жестко задаем путь, так как данные лежат вне проекта
BASE_DATA_DIR = Path(r"C:\bank\opt\data\external_data")

openapi_tags = {
    "name": TAG_NAME,
    "description": "Валидация файлов данных (CSV, Parquet, XLSX, XLS).",
}