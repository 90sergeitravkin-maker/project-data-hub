# src/back/app_datasets/config.py
"""Конфигурация app_datasets (унифицированно через AppConfig)."""
from pathlib import Path

from src.core.app_config import AppConfig
from src.core.env_loader import get_env

config = AppConfig.from_app_name(
    app_name="app_datasets",
    tag_name="APP Datasets",
    db_alias="app_datasets",
)

APP_NAME = config.app_name
TAG_NAME = config.tag_name
API_PREFIX_V1 = config.api_prefix
APP_VERSION = config.version
LOG_LEVEL = config.log_level
HOST = config.host
PORT = config.port
DB_ALIAS = config.db_alias

CONFIG_PATH = Path(get_env("APP_DATASET_CONFIG_PATH", "files/_fields_config.json"))
DATA_FILE_EXT = Path(get_env("APP_FAIL_MANAGER_EXT", ""))
openapi_tags = {
    "name": TAG_NAME,
    "description": "Хранение метаданных источников данных",
}