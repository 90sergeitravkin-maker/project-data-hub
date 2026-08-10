# src/back/app_monitor/config.py
"""
Конфигурация приложения app_monitor.
Мониторинг потребления ресурсов (RAM/CPU/IO) по приложениям.
"""
from src.core.app_config import AppConfig
from src.core.env_loader import get_env

config = AppConfig.from_app_name(
    app_name="app_monitor",
    tag_name="APP Monitor",
    db_alias="app_monitor",
)

# === Экспорт для обратной совместимости ===
APP_NAME = config.app_name
TAG_NAME = config.tag_name
API_PREFIX_V1 = config.api_prefix
LOG_LEVEL = config.log_level
HOST = config.host
PORT = config.port
DB_ALIAS = config.db_alias

# === Пороги алертинга ===
RAM_WARNING_MB = int(get_env("MONITOR_RAM_WARNING_MB", "512"))
RAM_CRITICAL_MB = int(get_env("MONITOR_RAM_CRITICAL_MB", "1024"))
SNAPSHOT_INTERVAL_SEC = int(get_env("MONITOR_SNAPSHOT_INTERVAL", "60"))
HISTORY_RETENTION_DAYS = int(get_env("MONITOR_HISTORY_DAYS", "7"))
TOP_N_HEAVY = int(get_env("MONITOR_TOP_N", "10"))

DISK_PATHS = []
for key in ["APP_FAIL_MANAGER_EXT", "APP_FAIL_MANAGER_RAW", "APP_FAIL_MANAGER_TEMP"]:
    val = get_env(key, "")
    if val:
        DISK_PATHS.append(val)

openapi_tags = {
    "name": TAG_NAME,
    "description": "Мониторинг потребления ресурсов (RAM/CPU) по приложениям. "
                   "Per-request трекинг, снимки памяти, алерты."
}
