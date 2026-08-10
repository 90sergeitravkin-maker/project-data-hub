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
from src.core.kafka import kafka_client
from src.core.kafka_admin import ensure_topics
from src.core.kafka_topics import get_required_topics
from src.core.env_loader import get_env
from src.back.app_ecomru.services import handle_download_task, handle_verification_task
from src.back.app_ecomru.config import (
    ensure_storage_ready,
    KAFKA_DOWNLOAD_TOPIC, KAFKA_DOWNLOAD_GROUP_ID,
    KAFKA_VERIFICATION_TOPIC, KAFKA_VERIFICATION_GROUP_ID,
)
from src.back.app_ecomru.check_data.config import PROCESS_FOLDER_TOPIC, PROCESS_FOLDER_GROUP_ID
from src.back.app_ecomru.check_data.services import handle_process_folder_task

SERVICE_LOG_LEVEL = get_env("SERVICE_LOG_LEVEL", "INFO").upper()
CORS_ORIGINS = [o.strip() for o in get_env("CORS_ORIGINS", "*").split(",") if o.strip()]
LOG_FILE = PROJECT_ROOT / "logs" / "app.log"

config_logging(level=SERVICE_LOG_LEVEL, log_file=LOG_FILE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Запуск Data Validation Service")

    # === Инициализация хранилища ===
    try:
        storage_path = ensure_storage_ready()
        logger.info(f"[STORAGE] Директория: {storage_path}")
    except (PermissionError, OSError, RuntimeError) as e:
        logger.critical(f"[STARTUP] Невозможно инициализировать хранилище: {e}")
        raise

    # === Kafka: создание топиков + запуск консьюмеров ===
    consumer_task = None
    try:
        # 1. Создаём все необходимые топики (идемпотентно)
        required_topics = get_required_topics()
        for topic_name in required_topics:
            await ensure_topics([topic_name], partitions=1, replication=1)
            logger.info(f"[KAFKA] Топик создан/проверен: {topic_name}")

        # 2. Запускаем продюсер
        await kafka_client.start()

        # 3. Регистрируем консьюмеры
        kafka_client.register_consumer(
            KAFKA_DOWNLOAD_TOPIC, KAFKA_DOWNLOAD_GROUP_ID, handle_download_task
        )
        kafka_client.register_consumer(
            KAFKA_VERIFICATION_TOPIC, KAFKA_VERIFICATION_GROUP_ID, handle_verification_task
        )
        kafka_client.register_consumer(
            PROCESS_FOLDER_TOPIC, PROCESS_FOLDER_GROUP_ID, handle_process_folder_task
        )

        # 4. Запускаем цикл консьюмеров
        consumer_task = asyncio.create_task(kafka_client.run_consumers())
        logger.info("[KAFKA] Консюмеры запущены")

    except Exception as e:
        logger.error(f"[KAFKA] Ошибка запуска: {e}", exc_info=True)

    yield  # ── Работа приложения ──

    # === Graceful shutdown ===
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass

    await kafka_client.stop()
    logger.info("Завершение работы...")


app = FastAPI(
    title="Data Validation Service",
    description="Модульная платформа для валидации и обработки данных",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=openapi_tags,
    swagger_ui_parameters={"docExpansion": "none"},
)

include_app_routers(app)
app.include_router(system_router, prefix="/api/v1/system")

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

    uvicorn.run(
        "src.main:app",
        host="127.0.0.1",
        port=8080,
        reload=True,
        log_level=SERVICE_LOG_LEVEL.lower(),
        access_log=True,
        log_config=get_uvicorn_log_config(  # ← ДОБАВЛЕНО
            level=SERVICE_LOG_LEVEL,
            log_file=LOG_FILE,
        ),
    )
