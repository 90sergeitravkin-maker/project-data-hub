# src/database/config.py
"""
Тонкая обёртка над src/core/db_config.py для обратной совместимости.
НЕ содержит дублирующейся логики — всё импортируется из core.
"""
from src.core.db_config import (
    ALIAS_TO_ENV,
    get_dsn,
    get_all_aliases,
    to_asyncpg_url,
)
from src.core.secrets import SecureDSN
from core.logger import logger


class DBConfig:
    """
    Класс-обёртка для обратной совместимости.
    Все методы делегируются в src/core/db_config.py
    """

    @classmethod
    def get_dsn(cls, alias: str) -> SecureDSN:
        """Делегирование в core.db_config.get_dsn()"""
        return get_dsn(alias)

    @classmethod
    def to_asyncpg_url(cls, alias: str) -> str:
        """Делегирование в core.db_config.to_asyncpg_url()"""
        return to_asyncpg_url(alias)

    @classmethod
    def get_all_aliases(cls) -> list[str]:
        """Делегирование в core.db_config.get_all_aliases()"""
        return get_all_aliases()


# Для обратной совместимости (если где-то импортируют напрямую)
DB_ALIASES = get_all_aliases()
ENV_MAP = ALIAS_TO_ENV
