# src/api.py
"""
API роутеры для общего сервиса.
Системные эндпоинты + подключение модулей приложений.
"""
from typing import List, Dict
from fastapi import APIRouter, status

from src.core.logger import logger

# === Глобальный список OpenAPI tags ===
openapi_tags: List[Dict[str, str]] = [
    {
        "name": "System",
        "Version": "System",
        "description": "Системные эндпоинты: здоровье, готовность, метрики"
    },
]


def _collect_app_openapi_tags() -> List[Dict[str, str]]:
    """
    Собирает openapi_tags из конфигов всех доступных приложений.
    Безопасно: пропускает отсутствующие модули и невалидные форматы.
    """
    collected = []
    apps = [
        # === Backend ===
        ("app_monitor",        "src.back.app_monitor.config"),
        ("app_users",           "src.back.app_users.config"),
        ("app_mail",           "src.back.app_mail.config"),
        ("app_ecomru",         "src.back.app_ecomru.config"),
        ("app_file_manager",   "src.back.app_file_manager.config"),
        ("app_data_registry",  "src.back.app_data_registry.config"),
        ("app_datasets",       "src.back.app_datasets.config"),
        ("app_text_dup_check", "src.back.app_text_dup_check.config"),
        ("app_link",           "src.back.app_link.config"),
        ("app_kafka",          "src.back.app_kafka.config"),
        # === Frontend ===
        ("web_monitor",        "src.front.web_monitor.config"),
        ("web_lk",             "src.front.web_lk.config"),
        ("web_file_manager",   "src.front.web_file_manager.config"),
        ("web_ecomru",         "src.front.web_ecomru.config"),
        ("web_datasets",       "src.front.web_datasets.config"),
        ("web_logs",           "src.front.web_logs.config"),
        ("web_architecture",   "src.back.web_architecture.config"),
    ]

    for app_name, config_path in apps:
        try:
            import importlib
            config_module = importlib.import_module(config_path)

            if hasattr(config_module, 'openapi_tags'):
                tag = config_module.openapi_tags
                if isinstance(tag, dict) and tag.get("name"):
                    if not any(t["name"] == tag["name"] for t in collected):
                        collected.append(tag)
                        logger.debug(f"Добавлен тег из {app_name}: {tag['name']}")
                elif isinstance(tag, list):
                    for t in tag:
                        if isinstance(t, dict) and t.get("name"):
                            if not any(existing["name"] == t["name"] for existing in collected):
                                collected.append(t)
                                logger.debug(f"Добавлен тег из {app_name}: {t['name']}")
        except ImportError:
            logger.debug(f"Приложение {app_name} не найдено (пропускаем)")
        except AttributeError as e:
            logger.warning(f"Ошибка при чтении тегов из {app_name}: {e}")
        except Exception as e:
            logger.error(f"Критическая ошибка сбора тегов из {app_name}: {e}", exc_info=True)

    return collected


# === Инициализируем теги при импорте ===
openapi_tags.extend(_collect_app_openapi_tags())

# === Глобальный роутер ===
router = APIRouter(tags=["System"])


# === СИСТЕМНЫЕ ЭНДПОИНТЫ ===
@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {
        "status": "ok",
        "message": "Data Hab Service is running",
        "version": "1.0.0",
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check():
    return {"status": "ready", "message": "Service is ready to accept traffic"}


@router.get("/metrics", status_code=status.HTTP_200_OK)
async def get_metrics():
    return {
        "service": "data_validation_service",
        "version": "1.0.0",
        "apps_connected": len([t for t in openapi_tags if t["name"] != "System"]),
    }


@router.get("/", status_code=status.HTTP_200_OK)
async def root():
    return {
        "service": "Data Validation Service",
        "version": "1.0.0",
        "documentation": "/docs",
        "health": "/api/v1/system/health",
        "applications": [
            # === Backend ===
            {"name": "src.back.app_mail",           "prefix": "/api/v1/app_mail"},
            {"name": "src.back.app_users",          "prefix": "/api/v1/app_users"},
            {"name": "src.back.app_file_manager",   "prefix": "/api/v1/app_file_manager"},
            {"name": "src.back.app_data_registry",  "prefix": "/api/v1/app_data_registry"},
            {"name": "src.back.app_datasets",       "prefix": "/api/v1/app_datasets"},
            {"name": "src.back.app_ecomru",         "prefix": "/api/v1/app_ecomru"},
            {"name": "src.back.app_text_dup_check", "prefix": "/api/v1/app_text_dup_check"},
            {"name": "src.back.app_link",           "prefix": "/api/v1/app_link"},
            {"name": "src.back.app_kafka",          "prefix": "/api/v1/app_kafka"},

            # === Frontend ===
            {"name": "src.front.web_lk",            "prefix": "/api/v1/web_lk"},
            {"name": "src.front.web_file_manager",  "prefix": "/api/v1/web_file_manager"},
            {"name": "src.front.web_ecomru",        "prefix": "/api/v1/web_ecomru"},
            {"name": "src.front.web_datasets",      "prefix": "/api/v1/web_datasets"},
            {"name": "src.front.web_architecture",  "prefix": "/api/v1/web_architecture"},
        ],
    }


# === Функция подключения роутеров приложений ===
def include_app_routers(app) -> None:
    """
    Подключает изолированные роутеры приложений.
    Каждое приложение импортируется только если существует.
    """
    apps_config = [
        # === Backend ===
        ("app_monitor",        "src.back.app_monitor.api",        "src.back.app_monitor.config"),
        ("app_mail",           "src.back.app_mail.api",           "src.back.app_mail.config"),
        ("app_file_manager",   "src.back.app_file_manager.api",   "src.back.app_file_manager.config"),
        ("app_text_dup_check", "src.back.app_text_dup_check.api", "src.back.app_text_dup_check.config"),
        ("app_data_registry",  "src.back.app_data_registry.api",  "src.back.app_data_registry.config"),
        ("app_datasets",       "src.back.app_datasets.api",       "src.back.app_datasets.config"),
        ("app_ecomru",         "src.back.app_ecomru.api",         "src.back.app_ecomru.config"),
        ("app_users",          "src.back.app_users.api",          "src.back.app_users.config"),
        ("app_link",           "src.back.app_link.api",           "src.back.app_link.config"),
        ("app_kafka",          "src.back.app_kafka.api",          "src.back.app_kafka.config"),
        # === Frontend ===
        ("web_monitor",        "src.front.web_monitor.api",       "src.front.web_monitor.config"),
        ("web_lk",             "src.front.web_lk.api",            "src.front.web_lk.config"),
        ("web_file_manager",   "src.front.web_file_manager.api",  "src.front.web_file_manager.config"),
        ("web_ecomru",         "src.front.web_ecomru.api",        "src.front.web_ecomru.config"),
        ("web_datasets",       "src.front.web_datasets.api",      "src.front.web_datasets.config"),
        ("web_logs",           "src.front.web_logs.api",          "src.front.web_logs.config"),
        ("web_architecture",   "src.front.web_architecture.api",  "src.front.web_architecture.config"),
    ]

    for app_key, api_path, config_path in apps_config:
        try:
            import importlib
            api_module = importlib.import_module(api_path)
            config_module = importlib.import_module(config_path)

            router = getattr(api_module, "router", None)
            prefix = getattr(config_module, "API_PREFIX_V1", None)
            tag = getattr(config_module, "TAG_NAME", app_key)

            if router and prefix:
                app.include_router(router, prefix=prefix)
                logger.info("✓ Подключено: %s → %s, %s, %s", app_key, api_path, tag, prefix)
            else:
                logger.warning(f"⚠ {app_key}: не найден router или API_PREFIX_V1")

        except (ImportError, AttributeError) as e:
            logger.warning(f"⚠ {app_key} не подключён: {type(e).__name__}: {e}")
        except Exception as e:
            logger.error(f"✗ Критическая ошибка подключения {app_key}: {e}", exc_info=True)
