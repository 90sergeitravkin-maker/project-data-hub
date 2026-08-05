# src/core/security.py
"""
Утилиты для аутентификации: хеширование паролей, JWT-токены.
"""

import bcrypt
from authx import AuthX, AuthXConfig
from src.core.env_loader import get_env, get_secret

# Загружаем конфигурацию JWT из окружения
JWT_SECRET = get_secret("JWT_SECRET_KEY", "change-me-in-production!").get_secret_value()
JWT_ALGORITHM = get_env("JWT_ALGORITHM", "HS256")
ACCESS_EXPIRE_MINUTES = int(get_env("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_EXPIRE_DAYS = int(get_env("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Инициализация authx
_authx_config = AuthXConfig()
_authx_config.JWT_SECRET_KEY = JWT_SECRET
_authx_config.JWT_ALGORITHM = JWT_ALGORITHM
_authx = AuthX(config=_authx_config)


def hash_password(password: str) -> str:
    """Хеширует пароль с помощью bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Проверяет пароль на соответствие хешу."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int) -> str:
    """Создаёт access-токен для пользователя."""
    return _authx.create_access_token(
        uid=str(user_id),
        expires_in=ACCESS_EXPIRE_MINUTES * 60
    )


def create_refresh_token(user_id: int) -> str:
    """Создаёт refresh-токен для пользователя."""
    return _authx.create_refresh_token(
        uid=str(user_id),
        expires_in=REFRESH_EXPIRE_DAYS * 24 * 60 * 60
    )


def decode_token(token: str) -> dict:
    """Декодирует JWT-токен и возвращает payload."""
    return _authx.decode_token(token)


def get_authx() -> AuthX:
    """Возвращает экземпляр AuthX (для случаев, когда нужен сам объект)."""
    return _authx
