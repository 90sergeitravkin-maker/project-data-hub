# src/database/security.py
import re
import os

from typing import Optional
from src.core.logger import logger


class SecureDSN:
    """Безопасная обёртка над строкой подключения."""
    _MASKED = "****"
    _PWD_RE = re.compile(r"(password|pwd)=([^&\s]*)", re.IGNORECASE)

    def __init__(self, dsn: Optional[str] = None):
        self._raw = dsn.strip() if dsn else ""
        self._masked = self._PWD_RE.sub(f"password={self._MASKED}", self._raw)

    @property
    def raw(self) -> str:
        return self._raw

    def __str__(self) -> str:
        return self._masked

    def __repr__(self) -> str:
        return f"<SecureDSN: {self._masked}>"

    def is_valid(self) -> bool:
        if not self._raw:
            return False
        # Базовая проверка формата postgresql://
        return self._raw.startswith(("postgresql://", "postgresql+asyncpg://"))


def load_dsn_from_env(env_key: str, fallback: Optional[str] = None) -> SecureDSN:
    """Безопасная загрузка DSN из .env с валидацией."""
    raw = os.getenv(env_key, fallback)
    dsn = SecureDSN(raw)
    if not dsn.is_valid():
        logger.warning(f"[DB_SECURITY] Некорректный или пустой DSN для {env_key}")
    return dsn