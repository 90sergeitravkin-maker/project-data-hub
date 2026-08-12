# src/core/env_loader.py
"""
Централизованная загрузка переменных окружения из .env.
"""

import os

from pathlib import Path
from dotenv import load_dotenv
from pydantic import SecretStr

from src.core.secrets import SecureString

# Определяем путь к .env (корень проекта)
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
print(ENV_PATH)
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)


def get_env(key: str, default: str = "") -> str:
    """
    Получить обычную (несекретную) переменную окружения.
    """
    return os.getenv(key, default)


def get_secret(key: str, default: str = "") -> SecretStr:
    """
    Получить секретную переменную, обёрнутую в Pydantic SecretStr.
    Это гарантирует маскировку при выводе.
    """
    value = os.getenv(key, default)
    return SecretStr(value)


def get_raw_secret(key: str, default: str = "") -> SecureString:
    """
    Получить секретную переменную в виде SecureString (аналог SecretStr).
    Используется для совместимости со старым кодом.
    """
    value = os.getenv(key, default)
    return SecureString(value)