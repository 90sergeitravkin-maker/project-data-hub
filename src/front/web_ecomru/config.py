from src.core.env_loader import get_env
from src.front.config import get_templates

APP_NAME = "web_ecomru"
TAG_NAME = "WEB Ecomru"
API_PREFIX_V1 = f"/api/v1/{APP_NAME}"
APP_VERSION = "1.0.0"

EXTERNAL_API_KEY = get_env("EXTERNAL_API_KEY", "")
EXTERNAL_API_URL = get_env("EXTERNAL_API_URL", "")
LINK = f"{EXTERNAL_API_URL}/api/v1/entities".rstrip("/")
HEADERS = {"Authorization": f"Bearer {EXTERNAL_API_KEY}"}
HOST = get_env("APP_ECOMRU_HOST", "127.0.0.1")
PORT = int(get_env("APP_ECOMRU_PORT", "8001"))
LOG_LEVEL = get_env("APP_ECOMRU_LOG_LEVEL", "DEBUG").upper()

templates = get_templates(APP_NAME)

openapi_tags = {
    "name": TAG_NAME,
    "version": APP_VERSION,
    "description": "Веб-интерфейс управления сущностями ECOMRU.",
}
