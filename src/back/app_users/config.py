# src/back/app_users/config.py
"""
Конфигурация приложения app_users.
"""
from src.core.app_config import AppConfig
from src.core.env_loader import get_env

config = AppConfig.from_app_name(
    app_name="app_users",
    tag_name="APP Auth",
    db_alias="app_users",
)

# === Экспорт базовых переменных ===
APP_NAME = config.app_name
TAG_NAME = config.tag_name
APP_VERSION = config.version
API_PREFIX_V1 = config.api_prefix
LOG_LEVEL = config.log_level
HOST = config.host
PORT = config.port
DB_ALIAS = config.db_alias

openapi_tags = [
    {
        "name": TAG_NAME,
        "description": "Аутентификация и управление профилем пользователя: регистрация, вход, токены, личный кабинет."
    }
]

# === JWT настройки ===
ACCESS_TOKEN_EXPIRE_MINUTES = config.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = config.refresh_token_expire_days
JWT_SECRET_KEY = config.jwt_secret.get_secret_value()
JWT_ALGORITHM = config.jwt_algorithm

# === Настройки кук ===
# ВАЖНО: Secure=True ТОЛЬКО для HTTPS! Для локальной разработки (HTTP) — False
JWT_COOKIE_SECURE = get_env("JWT_COOKIE_SECURE", "false").lower() in ("true", "1", "yes")
JWT_COOKIE_HTTPONLY = get_env("JWT_COOKIE_HTTPONLY", "true").lower() in ("true", "1", "yes")
JWT_COOKIE_SAMESITE = get_env("JWT_COOKIE_SAMESITE", "lax")
