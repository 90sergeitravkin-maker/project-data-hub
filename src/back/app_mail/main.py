# src/back/app_mail/main.py
"""
Точка входа приложения app_mail.
Использует фабрику create_app из core.
"""

import sys
from pathlib import Path
from src.core.app_factory import create_app
from src.back.app_mail.config import config
from src.back.app_mail.api import router
from src.back.app_mail.queue import mail_queue

# Добавляем корень проекта в sys.path (если нужно)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Опциональные хуки для старта/остановки очереди
async def on_startup(app):
    # Запуск очереди (если она ещё не запущена)
    if not mail_queue.is_running:
        await mail_queue.start()


async def on_shutdown(app):
    # Остановка очереди
    if mail_queue.is_running:
        await mail_queue.stop()


# Создаём приложение с хуками
app = create_app(
    config=config,
    router=router,
    on_startup=on_startup,
    on_shutdown=on_shutdown,
)

if __name__ == "__main__":
    import uvicorn

    print(f"🚀 Запуск app_mail на http://{config.host}:{config.port}")
    print(f"📚 Swagger UI: http://{config.host}:{config.port}/docs")

    uvicorn.run(
        "src.back.app_mail.main:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        log_level=config.log_level.lower(),
        access_log=True,
    )