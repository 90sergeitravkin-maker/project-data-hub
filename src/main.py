# src/main.py
import sys
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import HTMLResponse, RedirectResponse

SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent

from src.api import router as system_router, include_app_routers, openapi_tags
from src.core.logger import config_logging, logger, get_uvicorn_log_config
from src.core.env_loader import get_env

# ============================================================
# KAFKA - ПОЛНОСТЬЮ ВОССТАНОВЛЕНА
# ============================================================
from src.core.kafka import kafka_client
from src.core.kafka_admin import ensure_topics
from src.core.kafka_topics import get_required_topics
from src.back.app_ecomru.split_data.config import PROCESS_FOLDER_TOPIC, PROCESS_FOLDER_GROUP_ID
from src.back.app_ecomru.split_data.services import handle_process_folder_task
from src.back.app_ecomru.services import handle_download_task, handle_verification_task
from src.back.app_ecomru.config import (
    ensure_storage_ready,
    KAFKA_DOWNLOAD_TOPIC,
    KAFKA_DOWNLOAD_GROUP_ID,
    KAFKA_VERIFICATION_TOPIC,
    KAFKA_VERIFICATION_GROUP_ID,
)

# Импортируем модуль валидатора
try:
    from src.back.app_data_validator.api import router as validator_router
    from src.back.app_data_validator.config import (
        openapi_tags as validator_openapi_tags,
        API_PREFIX_V1 as validator_prefix
    )

    HAS_VALIDATOR = True
except ImportError as e:
    logger.warning(f"⚠️ app_data_validator не загружен: {e}")
    HAS_VALIDATOR = False

SERVICE_LOG_LEVEL = get_env("SERVICE_LOG_LEVEL", "INFO").upper()
CORS_ORIGINS = [o.strip() for o in get_env("CORS_ORIGINS", "*").split(",") if o.strip()]
LOG_FILE = PROJECT_ROOT / "logs" / "app.log"

config_logging(level=SERVICE_LOG_LEVEL, log_file=LOG_FILE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Запуск Data Validation Service с Kafka")

    # === Инициализация хранилища ===
    try:
        storage_path = ensure_storage_ready()
        logger.info(f"[STORAGE] Директория: {storage_path}")
    except Exception as e:
        logger.warning(f"[STORAGE] Пропуск инициализации: {e}")

    # === Инициализация Kafka ===
    try:
        # Запускаем продюсера
        await kafka_client.start()
        logger.info("[KAFKA] Продюсер запущен")

        # Создаём необходимые топики
        required_topics = get_required_topics()
        await ensure_topics(required_topics, partitions=3, replication=1)
        logger.info(f"[KAFKA] Топики созданы/проверены: {required_topics}")

        # Регистрируем обработчики
        kafka_client.register_consumer(
            KAFKA_DOWNLOAD_TOPIC,
            KAFKA_DOWNLOAD_GROUP_ID,
            handle_download_task
        )
        kafka_client.register_consumer(
            KAFKA_VERIFICATION_TOPIC,
            KAFKA_VERIFICATION_GROUP_ID,
            handle_verification_task
        )
        kafka_client.register_consumer(
            PROCESS_FOLDER_TOPIC,
            PROCESS_FOLDER_GROUP_ID,
            handle_process_folder_task
        )

        # Запускаем консьюмеров в фоновом режиме
        asyncio.create_task(kafka_client.run_consumers())
        logger.info("[KAFKA] Консьюмеры запущены")

    except Exception as e:
        logger.error(f"[KAFKA] Ошибка инициализации: {e}", exc_info=True)

    logger.info("✅ Приложение успешно запущено и готово принимать запросы!")

    yield  # ── Работа приложения ──

    # === Остановка Kafka ===
    logger.info("🛑 Завершение работы...")
    try:
        await kafka_client.stop()
        logger.info("[KAFKA] Клиент остановлен")
    except Exception as e:
        logger.error(f"[KAFKA] Ошибка остановки: {e}")


app = FastAPI(
    title="Data Validation Service",
    description="Модульная платформа для валидации и обработки данных",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=openapi_tags + ([validator_openapi_tags] if HAS_VALIDATOR else []),
    swagger_ui_parameters={"docExpansion": "none"},
)

include_app_routers(app)
app.include_router(system_router, prefix="/api/v1/system")

if HAS_VALIDATOR:
    app.include_router(validator_router, prefix=validator_prefix)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

static_path = PROJECT_ROOT / "src" / "front" / "static"
if not static_path.exists():
    static_path = SRC_DIR / "front" / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False, tags=["System"])
async def root_redirect():
    return RedirectResponse(url="/api/v1/web_lk/login", status_code=302)


if __name__ == "__main__":
    import uvicorn

    host = "127.0.0.1"
    port = 8001

    print("=" * 60)
    print(f"🚀 Сервер запущен: http://{host}:{port}")
    print(f"📚 Swagger UI:    http://{host}:{port}/docs")
    print("=" * 60)

    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=True,
        log_level=SERVICE_LOG_LEVEL.lower(),
        access_log=True,
        log_config=get_uvicorn_log_config(
            level=SERVICE_LOG_LEVEL,
            log_file=LOG_FILE,
        ),
    )