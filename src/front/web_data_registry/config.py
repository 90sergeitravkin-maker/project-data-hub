# src/front/web_data_registry/config.py
import os
from pathlib import Path
from dotenv import load_dotenv
from starlette.templating import Jinja2Templates
from src.front.config import get_templates

_env_path = Path(__file__).resolve().parents[2] / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path, override=True)

APP_NAME = "web_data_registry"
TAG_NAME = "WEB DATA REGISTRY"
API_PREFIX_V1 = f"/api/v1/{APP_NAME}"
APP_VERSION = "1.0.0"
templates: Jinja2Templates = get_templates(APP_NAME)

openapi_tags = {
    "name": TAG_NAME,
    "version": APP_VERSION,
    "description": "Веб-интерфейс "
}

HOST = os.getenv("APP_LK_HOST", "127.0.0.1")
PORT = int(os.getenv("APP_LK_PORT", "8001"))
LOG_LEVEL = os.getenv("APP_LK_LOG_LEVEL", "INFO").upper()
