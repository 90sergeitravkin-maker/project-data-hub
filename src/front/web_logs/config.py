from pathlib import Path
from src.core.env_loader import get_env
from src.front.config import get_templates

APP_NAME = "web_logs"
TAG_NAME = "WEB Logs"
API_PREFIX_V1 = f"/api/v1/{APP_NAME}"
APP_VERSION = "1.0.0"

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "app.log"
MAX_LINES = 200
HOST = get_env("APP_LOGS_HOST", "127.0.0.1")
PORT = int(get_env("APP_LOGS_PORT", "8006"))
LOG_LEVEL = get_env("APP_LOGS_LOG_LEVEL", "INFO").upper()

templates = get_templates(APP_NAME)

openapi_tags = {
    "name": TAG_NAME,
    "version": APP_VERSION,
    "description": "Просмотр последних строк логов приложения с фильтрами.",
}
