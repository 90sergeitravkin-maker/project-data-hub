# src/back/app_text_dup_check/main.py
import sys
from pathlib import Path
from src.core.app_factory import create_app
from src.back.app_text_dup_check.config import config
from src.back.app_text_dup_check.api import router

# Добавляем корень проекта в sys.path (если нужно)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Создаём приложение через фабрику
app = create_app(config, router)

if __name__ == "__main__":
    import uvicorn

    print(f"🚀 Запуск app_text_dup_check на http://{config.host}:{config.port}")
    print(f"📚 Swagger UI: http://{config.host}:{config.port}/docs")

    uvicorn.run(
        "src.back.app_text_dup_check.main:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        log_level=config.log_level.lower(),
        access_log=True,
    )
