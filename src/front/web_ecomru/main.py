# src/front/web_ecomru/main.py
"""
Точка входа приложения web_ecomru.
Изолированный FastAPI-сервис для веб-интерфейса ecomru.
"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # Указывает на src/
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.logger import logger
from src.front.web_ecomru.config import (
    APP_NAME, APP_VERSION, LOG_LEVEL, HOST, PORT,
    API_PREFIX_V1, openapi_tags
)
from src.front.web_ecomru.api import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    # === STARTUP ===
    try:
        logger.info(f"[{APP_NAME}] v{APP_VERSION} запущен")

        # При необходимости инициализации пула БД:
        # from src.database.manager import DBManager
        # db = DBManager()
        # await db.init_pool(alias="app_ecomru", min_size=2, max_size=10)

        yield
    except Exception as e:
        error_location = "src/front/web_ecomru, main.py, строка ~28"
        logger.critical(f"[{APP_NAME}] Критическая ошибка запуска: {e} | {error_location}")
        raise
    finally:
        # === SHUTDOWN ===
        logger.info(f"[{APP_NAME}] Завершение работы...")
        # await db.close_pool(alias="app_ecomru")


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[openapi_tags]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=API_PREFIX_V1)

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Запуск uvicorn: {HOST}:{PORT}")
    print(f"🌐 Swagger UI: http://{HOST}:{PORT}/docs")
    print(f"📖 ReDoc:     http://{HOST}:{PORT}/redoc")
    print(f"🌍 Web UI:    http://{HOST}:{PORT}{API_PREFIX_V1}/")

    uvicorn.run(
        "src.front.web_ecomru.main:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level=LOG_LEVEL.lower(),
        access_log=True,
    )
