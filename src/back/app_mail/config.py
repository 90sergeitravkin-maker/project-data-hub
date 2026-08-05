# src/back/app_mail/config.py
from src.core.app_config import AppConfig
from src.core.env_loader import get_env

config = AppConfig.from_app_name(
    app_name="app_mail",
    tag_name="APP Mail",
    db_alias="app_mail",
)

# === Экспорт базовых переменных ===
APP_NAME = config.app_name
TAG_NAME = config.tag_name
API_PREFIX_V1 = config.api_prefix
LOG_LEVEL = config.log_level
HOST = config.host
PORT = config.port
DB_ALIAS = config.db_alias

# === OpenAPI теги (ОБЯЗАТЕЛЬНО как переменная модуля, чтобы подхватил src/api.py) ===
openapi_tags = {
    "name": TAG_NAME,
    "description": "Отправка уведомлений через внешние сервисы: email"
}

# === SMTP настройки (специфичные для приложения) ===
SMTP_SERVER = get_env("APP_MAIL_SMTP_HOST", "")
SMTP_PORT = int(get_env("APP_MAIL_SMTP_PORT", "587"))
SMTP_USE_TLS = get_env("APP_MAIL_SMTP_TLS", "false").lower() in ("true", "1", "yes")
SMTP_USE_AUTH = get_env("APP_MAIL_SMTP_AUTH", "false").lower() in ("true", "1", "yes")
FROM_EMAIL = get_env("APP_MAIL_FROM_EMAIL", "test@test.com")
APP_PASSWORD = get_env("APP_MAIL_PASSWORD", "")
