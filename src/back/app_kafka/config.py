# src/back/app_kafka/config.py
from src.core.app_config import AppConfig

config = AppConfig.from_app_name(
    app_name="app_kafka",
    tag_name="APP Kafka",
    db_alias=None,
)

APP_NAME = config.app_name
TAG_NAME = config.tag_name
API_PREFIX_V1 = config.api_prefix
LOG_LEVEL = config.log_level
HOST = config.host
PORT = config.port

openapi_tags = {
    "name": TAG_NAME,
    "description": "Управление Kafka: просмотр топиков, групп, lag, отправка сообщений.",
}