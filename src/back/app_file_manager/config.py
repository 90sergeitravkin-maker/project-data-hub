# src/back/app_file_manager/config.py
from pathlib import Path
from src.core.app_config import AppConfig
from src.core.env_loader import get_env

config = AppConfig.from_app_name(
    app_name="app_file_manager",
    tag_name="APP File Manager",
    db_alias="app_file_manager",
)

# === Три корневые директории (для web_file_manager) ===
DATA_ROOT_EXT  = Path(get_env("APP_FAIL_MANAGER_EXT",  "-")).resolve()
DATA_ROOT_RAW  = Path(get_env("APP_FAIL_MANAGER_RAW",  "-")).resolve()
DATA_ROOT_TEMP = Path(get_env("APP_FAIL_MANAGER_TEMP", "-")).resolve()

# Для обратной совместимости (используется в app_file_manager API)
DATA_ROOT_DIR = DATA_ROOT_EXT

# Реестр доступных корней (whitelist — безопасность)
AVAILABLE_ROOTS = {
    "ext":  {"path": DATA_ROOT_EXT,  "label": "📦 External (EXT)",  "env": "APP_FAIL_MANAGER_EXT"},
    "raw":  {"path": DATA_ROOT_RAW,  "label": "🗂 Raw (RAW)",       "env": "APP_FAIL_MANAGER_RAW"},
    "temp": {"path": DATA_ROOT_TEMP, "label": "🧪 Temp (TEST)",     "env": "APP_FAIL_MANAGER_TEMP"},
}

# === Токены ===
_raw_token = get_env("APP_SYSTEMS_TOKEN", "")
APP_TOKEN = [t.strip().strip('"').strip("'") for t in _raw_token.split(",") if t.strip()]

# === Экспорт базовых переменных для обратной совместимости ===
APP_NAME = config.app_name
TAG_NAME = config.tag_name
API_PREFIX_V1 = config.api_prefix
LOG_LEVEL = config.log_level
HOST = config.host
PORT = config.port
RELOAD = config.reload

openapi_tags = {
    "name": TAG_NAME,
    "description": "Мониторинг доступности файлов и извлечение схем данных."
}