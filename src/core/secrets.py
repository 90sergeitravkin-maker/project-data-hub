# src/core/secrets.py
"""
Безопасные строки и DSN для скрытия секретов в логах и отладке.
"""

import re
from typing import Optional


class SecureString(str):
    """
    Строка, которая маскирует своё содержимое при преобразовании в str/repr.
    Используется для хранения паролей, токенов и других секретов.
    """
    def __str__(self) -> str:
        return "(********)"

    def __repr__(self) -> str:
        return "(********)"

    def __format__(self, format_spec: str) -> str:
        return "(********)"

    def __getattribute__(self, name: str):
        # Запрещаем доступ к методам, которые могут раскрыть содержимое
        if name in ('__reduce__', '__reduce_ex__', '__getnewargs__', '__getstate__'):
            raise AttributeError(f"Доступ к методу '{name}' запрещён")
        return super().__getattribute__(name)

    def get_raw(self) -> str:
        """Возвращает исходное значение (только для внутреннего использования)."""
        return super().__str__()


class SecureDSN:
    """
    Безопасная обёртка над строкой подключения к БД.
    Маскирует пароль при выводе.
    """
    _PWD_RE = re.compile(r"(password|pwd)=([^&\s]*)", re.IGNORECASE)

    def __init__(self, dsn: Optional[str] = None):
        self._raw = dsn.strip() if dsn else ""
        self._masked = self._PWD_RE.sub(r"password=****", self._raw)

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
        return self._raw.startswith(("postgresql://", "postgresql+asyncpg://"))