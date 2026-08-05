# src/front/web_architecture/config.py
from src.front.config import get_templates

APP_NAME = "web_architecture"
TAG_NAME = "WEB Architecture"
API_PREFIX_V1 = "/api/v1/web_architecture"

templates = get_templates(APP_NAME)

openapi_tags = {
    "name": TAG_NAME,
    "description": "Визуализация архитектуры приложения",
}