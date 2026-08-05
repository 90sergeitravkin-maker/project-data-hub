# src/back/app_link/config.py
import os

from src.core.app_config import AppConfig

config = AppConfig.from_app_name(
    app_name="app_link",
    tag_name="APP Link",
    db_alias="app_link",
)

APP_NAME = config.app_name
TAG_NAME = config.tag_name
API_PREFIX_V1 = config.api_prefix
LOG_LEVEL = config.log_level
HOST = config.host
PORT = config.port
DB_ALIAS = config.db_alias
APP_KAFKA_URL     = os.getenv("APP_KAFKA_URL", "http://127.0.0.1:8081/api/v1/app_kafka")
KAFKA_TOPIC_LINKS = os.getenv("APP_LINK_KAFKA_TOPIC", "links-topic")

openapi_tags = {
    "name": TAG_NAME,
    "description": "Управление списком ссылок с дедупликацией, нормализацией и хешированием.",
}
