# src/core/db_config.py
"""
Централизованная конфигурация подключений к базам данных.
ЕДИНСТВЕННЫЙ источник истины для алиасов БД.
"""
from typing import Dict

from src.core.env_loader import get_env
from src.core.secrets import SecureDSN

# === Маппинг алиасов БД → переменные окружения ===
ALIAS_TO_ENV: Dict[str, str] = {
    "base_01":            "DB_LOCAL_01",
    "app_users":          "APP_USER_DB",
    "app_file_manager":   "APP_SYSTEMS_DB",
    "app_servises":       "APP_SERVICES_DB",
    "app_data_registry":  "APP_DATA_REGISTRY_DB",
    "app_ecomru":         "APP_ECOMRU_DB",
    "app_mail":           "APP_MAIL_DB",
    "app_text_dup_check": "APP_TEXT_DUPE_CHECK_DB",
    "app_datasets":       "APP_DATASET_DB",
    "app_monitor":        "APP_MONITOR_DB",
    "app_link":           "APP_LINK_DB",
}

# === Маппинг алиасов → search_path (для изоляции схем) ===
SCHEMA_MAP: Dict[str, str] = {
    "app_ecomru":         "app_ecomru,public",
    "app_file_manager":   "app_file_manager,public",
    "app_data_registry":  "app_data_registry,public",
    "app_servises":       "app_servises,public",
    "base_01":            "public",
    "app_users":          "app_users",
    "app_mail":           "app_mail,public",
    "app_text_dup_check": "app_text_dup_check,public",
    "app_datasets":       "app_datasets,public",
    "app_monitor":        "app_monitor,public",
    "app_link":           "app_link",
}

# === Кэш DSN ===
_dsn_cache: Dict[str, SecureDSN] = {}


def get_dsn(alias: str) -> SecureDSN:
    """
    Возвращает SecureDSN для указанного алиаса.
    Кеширует результат.
    """
    if alias not in _dsn_cache:
        env_key = ALIAS_TO_ENV.get(alias)
        if not env_key:
            raise ValueError(f"Неизвестный алиас БД: {alias}")
        raw = get_env(env_key)
        if not raw:
            raise ValueError(f"Переменная окружения {env_key} не задана для алиаса {alias}")
        _dsn_cache[alias] = SecureDSN(raw)
    return _dsn_cache[alias]


def get_search_path(alias: str) -> str:
    """Возвращает search_path для алиаса (по умолчанию 'public')."""
    return SCHEMA_MAP.get(alias, "public")


def get_all_aliases() -> list[str]:
    """Возвращает список всех зарегистрированных алиасов БД."""
    return list(ALIAS_TO_ENV.keys())


def to_asyncpg_url(alias: str) -> str:
    """
    Преобразует DSN в формат для asyncpg.
    postgresql:// → postgresql+asyncpg://
    """
    dsn = get_dsn(alias)
    return dsn.raw.replace("postgresql://", "postgresql+asyncpg://", 1)