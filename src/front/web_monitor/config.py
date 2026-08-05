# src/front/web_monitor/config.py
from src.core.env_loader import get_env
from src.front.config import get_templates

APP_NAME = "web_monitor"
TAG_NAME = "WEB Monitor"
API_PREFIX_V1 = f"/api/v1/{APP_NAME}"
APP_VERSION = "1.0.0"
HOST = get_env("APP_MONITOR_HOST", "127.0.0.1")
PORT = int(get_env("APP_MONITOR_PORT", "8008"))
LOG_LEVEL = get_env("APP_MONITOR_LOG_LEVEL", "INFO").upper()

templates = get_templates(APP_NAME)

openapi_tags = {
    "name": TAG_NAME,
    "version": APP_VERSION,
    "description": "Веб-интерфейс мониторинга потребления ресурсов (RAM/CPU).",
}