# src/front/web_file_manager/config.py
"""
Конфигурация frontend-модуля web_file_manager.
Все шаблоны хранятся в src/front/templates/web_file_manager/
"""
from pathlib import Path
from src.core.env_loader import get_env

# === Основные параметры приложения ===
APP_NAME = "web_file_manager"
TAG_NAME = "WEB FILE MANAGER"
API_PREFIX_V1 = f"/api/v1/{APP_NAME}"
APP_VERSION = "1.0.0"

# === Сетевые параметры ===
HOST = get_env("APP_FILE_MANAGER_HOST", "127.0.0.1")
PORT = int(get_env("APP_FILE_MANAGER_PORT", "8005"))
LOG_LEVEL = get_env("APP_FILE_MANAGER_LOG_LEVEL", "INFO").upper()

# === Безопасная инициализация templates ===
try:
    from src.front.config import get_templates
    templates = get_templates(APP_NAME)
except Exception as e:
    # Fallback: если get_templates недоступен, создаём напрямую
    import sys
    print(f"[WARNING] web_file_manager: не удалось импортировать get_templates: {e}", file=sys.stderr)
    from jinja2 import ChoiceLoader, FileSystemLoader, Environment
    from starlette.templating import Jinja2Templates

    _shared_templates = Path(__file__).resolve().parent.parent / "templates"
    _loaders = [FileSystemLoader(str(_shared_templates))]

    _env = Environment(loader=ChoiceLoader(_loaders), autoescape=True)
    _env.globals["static"] = lambda p: f"/static/{p.lstrip('/')}"
    templates = Jinja2Templates(env=_env)

# === OpenAPI теги ===
openapi_tags = {
    "name": TAG_NAME,
    "version": APP_VERSION,
    "description": "Веб-интерфейс управления файлами: просмотр папок, загрузка, скачивание. "
                   "Поддержка трёх корневых директорий: EXT, RAW, TEMP.",
}