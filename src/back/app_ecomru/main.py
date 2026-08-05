# # src/app_ecomru/main.py
# """
# Точка входа приложения app_ecomru.
# Изолированный FastAPI-сервис для работы с данными ECOMRU.
# """
# import sys
# from pathlib import Path
# from contextlib import asynccontextmanager
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
#
# PROJECT_ROOT = Path(__file__).resolve().parents[2]
# if str(PROJECT_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECT_ROOT))
#
# from src.config.logger import config_logging, logger
# from src.app_ecomru.config import (
#     APP_NAME,
#     APP_VERSION,
#     LOG_LEVEL,
#     HOST,
#     PORT,
#     RELOAD,
#     ensure_storage_ready,
#     DB_ALIAS,
# )
# from src.database.manager import DBManager
# from src.app_ecomru.api import router as ecomru_router, init_queue, shutdown_queue
#
#
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """Управление жизненным циклом приложения."""
#     # === STARTUP ===
#     logger.info(f"[{APP_NAME}] Запуск v{APP_VERSION}")
#
#     # Инициализация хранилища
#     storage_path = ensure_storage_ready()
#     logger.info(f"[STORAGE] Директория: {storage_path}")
#
#     # Инициализация пула БД ТОЛЬКО для этого приложения
#     db_manager = DBManager()
#     try:
#         await db_manager.init_pool(DB_ALIAS, min_size=1, max_size=5)
#         logger.info(f"[DB] Пул '{DB_ALIAS}' инициализирован")
#     except Exception as e:
#         logger.error(f"[DB] Критическая ошибка инициализации пула '{DB_ALIAS}': {e}")
#         # Не останавливаем приложение, но логируем ошибку
#
#     # Инициализация очереди скачивания
#     await init_queue()
#
#     yield
#
#     # === SHUTDOWN ===
#     logger.info(f"[{APP_NAME}] Завершение работы...")
#
#     # Остановка очереди
#     await shutdown_queue()
#
#     # Закрытие пула БД ТОЛЬКО для этого приложения (изоляция!)
#     try:
#         await db_manager.close_pool(DB_ALIAS)
#         logger.info(f"[DB] Пул '{DB_ALIAS}' закрыт")
#     except Exception as e:
#         logger.warning(f"[DB] Ошибка закрытия пула '{DB_ALIAS}': {e}")
#
#     logger.info(f"[{APP_NAME}] Остановлен")
#
#
# app = FastAPI(
#     title=APP_NAME,
#     description="Сервис получения и скачивания данных ECOMRU",
#     version=APP_VERSION,
#     lifespan=lifespan,
#     docs_url="/docs",
#     redoc_url="/redoc",
#     openapi_url="/openapi.json",
# )
#
# # CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
# # Подключение роутеров
# app.include_router(ecomru_router, prefix="/api/v1/ecomru")
#
#
# if __name__ == "__main__":
#     import uvicorn
#
#     config_logging(level=LOG_LEVEL, log_base_path=PROJECT_ROOT)
#     logger.info(f"Запуск uvicorn: {HOST}:{PORT}")
#     print(f"📚 Swagger UI: http://{HOST}:{PORT}/docs")
#     print(f"🔍 ReDoc:     http://{HOST}:{PORT}/redoc")
#
#     uvicorn.run(
#         "src.app_ecomru.main:app",
#         host=HOST,
#         port=PORT,
#         reload=RELOAD,
#         log_level=LOG_LEVEL.lower(),
#         access_log=True,
#     )