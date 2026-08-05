# src/front/config.py
from pathlib import Path
from jinja2 import ChoiceLoader, FileSystemLoader, Environment
from starlette.templating import Jinja2Templates

# Корневая директория фронтенда
FRONT_ROOT = Path(__file__).resolve().parent
SHARED_TEMPLATES_DIR = FRONT_ROOT / "templates"
SHARED_PARTIALS_DIR = SHARED_TEMPLATES_DIR / "partials"


def get_templates(app_name: str) -> Jinja2Templates:
    """
    Создаёт и возвращает настроенный Jinja2Templates для указанного приложения.
    Все шаблоны лежат в src/front/templates/{app_name}/*.html.
    """
    loaders = [
        FileSystemLoader(str(SHARED_TEMPLATES_DIR)),  # src/front/templates
    ]

    if SHARED_PARTIALS_DIR.exists():
        loaders.append(FileSystemLoader(str(SHARED_PARTIALS_DIR)))

    env = Environment(
        loader=ChoiceLoader(loaders),
        autoescape=True
    )

    # Глобальная функция для генерации путей к статике
    env.globals["static"] = lambda path: f"/static/{path.lstrip('/')}"

    return Jinja2Templates(env=env)


# Для обратной совместимости
templates = get_templates("base")