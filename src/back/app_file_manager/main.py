# src/back/app_file_manager/main.py
import sys
from pathlib import Path
from src.core.app_factory import create_app
from src.back.app_file_manager.config import config
from src.back.app_file_manager.api import router

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

app = create_app(config, router)

if __name__ == "__main__":
    import uvicorn

    print(f"🚀 Запуск app_file_manager на http://{config.host}:{config.port}")
    print(f"📚 Swagger UI: http://{config.host}:{config.port}/docs")

    uvicorn.run(
        "src.back.app_file_manager.main:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        log_level=config.log_level.lower(),
        access_log=True,
    )