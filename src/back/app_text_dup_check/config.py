# src/back/app_text_dup_check/config.py
from src.core.app_config import AppConfig

# Создаём конфиг через фабричный метод
config = AppConfig.from_app_name(
    app_name="app_text_dup_check",
    tag_name="APP Text Dup Check",
    db_alias="app_text_dup_check",
)

# Экспорт основных переменных (для обратной совместимости)
APP_NAME = config.app_name
TAG_NAME = config.tag_name
API_PREFIX_V1 = config.api_prefix
LOG_LEVEL = config.log_level
HOST = config.host
PORT = config.port
DB_ALIAS = config.db_alias

openapi_tags = {
    "name": TAG_NAME,
    "description": "Сервис проверки текстов на дубликаты с оценкой схожести (1-100%)."
}
