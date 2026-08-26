from src.core.env_loader import get_env
from src.front.config import get_templates

APP_NAME = "web_datasets"
TAG_NAME = "WEB DATASETS"
API_PREFIX_V1 = f"/api/v1/{APP_NAME}"
APP_VERSION = "1.0.0"
HOST = get_env("APP_DATASETS_HOST", "127.0.0.1")
PORT = int(get_env("APP_DATASETS_PORT", "8001"))
LOG_LEVEL = get_env("APP_DATASETS_LOG_LEVEL", "INFO").upper()

templates = get_templates(APP_NAME)

openapi_tags = {
    "name": TAG_NAME,
    "version": APP_VERSION,
    "description": "Веб-интерфейс просмотра и агрегации датасетов.",
}
