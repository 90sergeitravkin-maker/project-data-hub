from contextlib import asynccontextmanager
from typing import Optional, Callable, Awaitable
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from src.core.app_config import AppConfig
from src.core.logger import config_logging
from src.database.manager import DBManager

def create_app(
    config: AppConfig,
    router: APIRouter,
    *,
    on_startup: Optional[Callable[[FastAPI], Awaitable[None]]] = None,
    on_shutdown: Optional[Callable[[FastAPI], Awaitable[None]]] = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config_logging(level=config.log_level)
        db_manager = None
        if config.db_alias:
            db_manager = DBManager()
            try:
                await db_manager.init_pool(
                    alias=config.db_alias,
                    min_size=2,
                    max_size=10,
                    search_path=config.get_search_path()
                )
            except Exception as e:
                raise RuntimeError(f"Не удалось инициализировать пул БД: {e}")
        if on_startup:
            await on_startup(app)
        yield
        if on_shutdown:
            await on_shutdown(app)
        if db_manager and config.db_alias:
            await db_manager.close_pool(config.db_alias)

    app = FastAPI(
        title=config.tag_name,
        version=config.version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=config.openapi_tags
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix=config.api_prefix)
    return app