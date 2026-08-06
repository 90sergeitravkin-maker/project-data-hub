# src/back/app_data_registry/config.py
from src.core.app_config import AppConfig
from src.core.env_loader import get_env

config = AppConfig.from_app_name(
    app_name="app_data_registry",
    tag_name="APP Data Registry",
    db_alias="app_data_registry",
)

# Специфичные параметры
CHECK_DATA_URL      = get_env("CHECK_DATA_ENDPOINT", "http://localhost:8000/api/v1/systems/check-data")
CHECK_TIMEOUT       = int(get_env("CHECK_DATA_TIMEOUT", "30"))
CHECK_SERVICE_TOKEN = get_env("APP_SYSTEMS_TOKEN", "").split(',')[0] if get_env("APP_SYSTEMS_TOKEN") else ""

# Экспорт базовых переменных для обратной совместимости
APP_NAME = config.app_name
TAG_NAME = config.tag_name
API_PREFIX_V1 = config.api_prefix
LOG_LEVEL = config.log_level
HOST = config.host
PORT = config.port
DB_ALIAS = config.db_alias

openapi_tags = {
    "name": TAG_NAME,
    "description": "Реестр сервисов и источников данных. Маршрутизация проверок в /systems/check-data."
}
