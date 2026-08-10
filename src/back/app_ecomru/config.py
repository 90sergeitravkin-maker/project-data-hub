# src/back/app_ecomru/config.py
"""Конфигурация приложения app_ecomru."""
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

from src.core.logger import logger

# Загрузка .env из корня проекта
_env_path = Path(__file__).resolve().parents[3] / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path, override=True)
    logger.debug(f"[CONFIG] .env загружен: {_env_path}")

CONFIG_PATH = Path(_env_path).parent / "files" / "_fields_config.json"


# ============================================================
# HOT-RELOAD конфиг полей (читается при каждом вызове)
# ============================================================
def _normalize_keys(obj: Any) -> Any:
    """
    Рекурсивно убирает пробелы из ключей dict и строковых значений.
    В _fields_config.json ключи и значения содержат пробелы в конце.
    """
    if isinstance(obj, dict):
        return {k.strip(): _normalize_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_keys(item) for item in obj]
    if isinstance(obj, str):
        return obj.strip()
    return obj


def load_fields_config() -> Dict[str, Any]:
    """
    Читает _fields_config.json с диска КАЖДЫЙ раз (hot-reload).
    Нормализует пробелы в ключах и значениях.
    """
    if not CONFIG_PATH.is_file():
        logger.error(f"[CONFIG] Файл конфигурации не найден: {CONFIG_PATH}")
        return {}
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        return _normalize_keys(raw)
    except json.JSONDecodeError as e:
        logger.error(f"[CONFIG] Ошибка синтаксиса JSON в {CONFIG_PATH}: {e}")
        return {}


def get_allowed_prefixes() -> List[str]:
    """Возвращает список разрешённых entity (hot-reload)."""
    return list(load_fields_config().keys())


def get_split_columns(entity: str) -> List[str]:
    """
    Возвращает список столбцов для разбиения по entity (hot-reload).

    Поддерживает два формата в _fields_config.json:
      1. Простой список:  {"ENTITY": ["col1", "col2"]}
      2. Объект:          {"ENTITY": {"processing": {"split_column": ["col1"]}}}
    """
    if not entity:
        return []

    config = load_fields_config()  # читаем файл каждый раз
    entity_cfg = config.get(entity.strip())
    if entity_cfg is None:
        logger.debug(f"[CONFIG] entity '{entity}' не найден в {CONFIG_PATH.name}")
        return []

    # Формат 1: простой список столбцов
    if isinstance(entity_cfg, list):
        return [c for c in entity_cfg if isinstance(c, str) and c]

    # Формат 2: объект с processing.split_column
    if isinstance(entity_cfg, dict):
        processing = entity_cfg.get("processing", {})
        if isinstance(processing, dict):
            cols = processing.get("split_columns", [])
            if isinstance(cols, list):
                return [c for c in cols if isinstance(c, str) and c]
            if isinstance(cols, str) and cols:
                return [cols]

    return []


# Для обратной совместимости (нормализовано при старте)
ALLOWED_PREFIXES = get_allowed_prefixes()

# === Основные параметры приложения ===
APP_NAME = "app_ecomru"
TAG_NAME = "APP Ecomru"
APP_VERSION = "1.1.0"
API_PREFIX_V1 = f"/api/v1/{APP_NAME}"

# Логирование и сеть
LOG_LEVEL = os.getenv("ECOMRU_LOG_LEVEL", "DEBUG").upper()
HOST = os.getenv("ECOMRU_HOST", "127.0.0.1")
PORT = int(os.getenv("ECOMRU_PORT", 8001))
RELOAD = os.getenv("APP_ECOMRU_RELOAD", "true").lower() in ("true", "1", "yes")

# KAFKA
APP_KAFKA_URL = os.getenv("APP_KAFKA_URL", "http://127.0.0.1:8081/api/v1/app_kafka")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

KAFKA_DOWNLOAD_TOPIC = os.getenv("APP_ECOMRU_KAFKA_TOPIC_DOWNLOAD", "ecomru-download")
KAFKA_DOWNLOAD_GROUP_ID = os.getenv("APP_ECOMRU_KAFKA_GROUP_ID_DOWNLOAD", "ecomru-download-group")

KAFKA_VERIFICATION_TOPIC = os.getenv("APP_ECOMRU_KAFKA_TOPIC_VERIFICATION", "ecomru-verification")
KAFKA_VERIFICATION_GROUP_ID = os.getenv("APP_ECOMRU_KAFKA_GROUP_ID_VERIFICATION", "ecomru-verification-group")

KAFKA_TRANSFER_TOPIC = os.getenv("APP_ECOMRU_KAFKA_TOPIC_TRANSFER", "ecomru-transfer")
KAFKA_TRANSFER_GROUP_ID = os.getenv("APP_ECOMRU_KAFKA_GROUP_ID_TRANSFER", "ecomru-transfer-group")

DATA_FILE_EXT = Path(os.getenv("APP_FAIL_MANAGER_EXT", ""))
DATA_FILE_RAW = Path(os.getenv("APP_FAIL_MANAGER_RAW", ""))
DATA_FILE_TEMP = Path(os.getenv("APP_FAIL_MANAGER_TEMP", ""))
MAX_FILE_SIZE = 120 * 1024 * 1024

# === Строгая изоляция БД ===
DB_ALIAS = os.getenv("ECOMRU_DB_ALIAS", "app_ecomru")

# Параметры скачивания
ECOMRU_VERIFY_SHA256 = False
ECOMRU_CHUNK_SIZE = 262144
ECOMRU_DOWNLOAD_WORKERS = 8
ECOMRU_RATE_PER_SECOND = 0

MAX_CONCURRENT = int(os.getenv("ECOMRU_MAX_CONCURRENT", "5"))
DOWNLOAD_TIMEOUT = int(os.getenv("ECOMRU_DOWNLOAD_TIMEOUT", "300"))
DOWNLOAD_RETRIES = int(os.getenv("ECOMRU_DOWNLOAD_RETRIES", "3"))

EXTERNAL_API_URL = os.getenv("EXTERNAL_API_URL", "")
EXTERNAL_API_KEY = os.getenv("EXTERNAL_API_KEY", "")
ENTITIES_ENDPOINT = f"{EXTERNAL_API_URL}/api/v1/entities" if EXTERNAL_API_URL else ""

openapi_tags = {
    "name": TAG_NAME,
    "description": "Реестр сервисов и источников данных. Маршрутизация проверок в /systems/check-data."
}

DISK_SPACE_SAFETY_FACTOR = 2 * 1024 * 1024 * 1024  # 2 ГБ в байтах
KAFKA_REPORT_TOPIC = os.getenv("APP_ECOMRU_KAFKA_TOPIC_REPORT", "ecomru-report")
KAFKA_REPORT_GROUP_ID = os.getenv("APP_ECOMRU_KAFKA_GROUP_ID_REPORT", "ecomru-report-group")


def ensure_storage_ready() -> Path:
    """Инициализация директории хранения. Вызывается в lifespan."""
    try:
        if not DATA_FILE_RAW.parent.exists():
            try:
                DATA_FILE_RAW.parent.mkdir(parents=True, exist_ok=True)
            except PermissionError as e:
                logger.critical(
                    f"[CONFIG] Нет прав на создание директории: {DATA_FILE_RAW.parent}. "
                    f"Проверьте переменную EXTERNAL_FILE в .env. Ошибка: {e}"
                )
                raise RuntimeError(
                    f"Невозможно создать хранилище: {DATA_FILE_RAW}. "
                    f"Укажите доступный путь в переменной EXTERNAL_FILE"
                ) from e

        DATA_FILE_RAW.mkdir(parents=True, exist_ok=True)
        logger.info(f"[CONFIG] Хранилище готово: {DATA_FILE_RAW}")
        return DATA_FILE_RAW

    except Exception as e:
        logger.critical(f"[CONFIG] Критическая ошибка инициализации хранилища: {e}", exc_info=True)
        raise
