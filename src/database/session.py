# src/database/session.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from src.core.logger import logger
from src.core.db_config import to_asyncpg_url


_engines = {}
_factories = {}


def get_engine(alias: str):
    if alias not in _engines:
        url = to_asyncpg_url(alias)  # ← Используем функцию из core
        _engines[alias] = create_async_engine(url, echo=False, pool_pre_ping=True, pool_size=5)
        logger.info(f"[DB_SESSION] Engine создан: {alias}")
    return _engines[alias]


def get_session_factory(alias: str) -> async_sessionmaker[AsyncSession]:
    if alias not in _factories:
        engine = get_engine(alias)
        _factories[alias] = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return _factories[alias]


async def get_async_session(alias: str = "base_01") -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory(alias)
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
