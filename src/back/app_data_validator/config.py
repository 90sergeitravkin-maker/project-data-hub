# src/back/app_data_validator/config.py
from pathlib import Path
from src.core.env_loader import get_env

APP_NAME = "app_data_validator"
TAG_NAME = "APP Data Validator"
API_PREFIX_V1 = "/api/v1/validator"

# Жестко задаем путь, так как данные лежат вне проекта
BASE_DATA_DIR = Path(get_env("APP_FAIL_MANAGER_RAW")).resolve()

# === Kafka ===
KAFKA_VALIDATION_INPUT_TOPIC = get_env(
    "APP_VALIDATOR_KAFKA_TOPIC_INPUT", "ecomru-verification"
)
KAFKA_VALIDATION_INPUT_GROUP = get_env(
    "APP_VALIDATOR_KAFKA_GROUP_ID", "data-validator-group"
)
KAFKA_VALIDATION_OUTPUT_TOPIC = get_env(
    "APP_VALIDATOR_KAFKA_TOPIC_OUTPUT", "ecomru-validation"
)

openapi_tags = {
    "name": TAG_NAME,
    "description": """
    Валидация каждой строки файла по типу данных и сопоставление со справочником.
    Обрабатывает файлы типа (CSV, Parquet, XLSX, XLS).
    """,
}