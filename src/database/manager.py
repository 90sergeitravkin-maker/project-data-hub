# src/database/manager.py
"""
Менеджер пулов соединений asyncpg для изолированных приложений.
- Каждое приложение инициализирует ТОЛЬКО свой пул по алиасу
- Все взаимодействия с БД строго через этот класс
- Поддержка изолированного shutdown через close_pool(alias)
- Python 3.12 + asyncpg + PostgreSQL 15
"""
import asyncio
import asyncpg
import psycopg2
from contextlib import asynccontextmanager, contextmanager
from typing import Optional, Dict, Any, List, AsyncGenerator, TypeVar
from src.core.logger import logger
from src.database.config import DBConfig
from src.core.type_unifier import SchemaComparator

T = TypeVar("T")


class DBManager:
    """
    Singleton-менеджер асинхронных пулов соединений.
    Архитектурные гарантии:
    - _pools[alias] хранит пул строго по алиасу приложения
    - Нет кросс-доступа: app_data_registry не видит pool app_file_manager
    - Изолированный shutdown: close_pool(alias) закрывает только нужный пул
    """
    _instance: Optional["DBManager"] = None
    _pools: Dict[str, asyncpg.Pool] = {}
    _init_lock: asyncio.Lock = asyncio.Lock()

    # Кэш компаратора схем (дорогая инициализация)
    _comparator: Optional[SchemaComparator] = None

    def __new__(cls) -> "DBManager":
        """Singleton паттерн: один экземпляр на процесс."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def _get_comparator(cls) -> SchemaComparator:
        """Ленивая инициализация SchemaComparator."""
        if cls._comparator is None:
            cls._comparator = SchemaComparator()
        return cls._comparator

    async def init_pool(
            self,
            alias: str,
            min_size: int = 1,
            max_size: int = 10,
            search_path: Optional[str] = None,
    ) -> asyncpg.Pool:
        """
        Инициализация пула соединений для указанного алиаса БД.

        Args:
            alias: Алиас БД (должен быть зарегистрирован в DBConfig)
            min_size: Минимальное количество соединений в пуле
            max_size: Максимальное количество соединений в пуле
            search_path: PostgreSQL search_path (если None, берётся из SCHEMA_MAP)

        Returns:
            asyncpg.Pool: Созданный или существующий пул

        Raises:
            ValueError: Если алиас не зарегистрирован
            RuntimeError: Если не удалось подключиться к БД
        """
        async with self._init_lock:
            if alias in self._pools:
                return self._pools[alias]

            try:
                secure_dsn = DBConfig.get_dsn(alias)
                url = secure_dsn.raw

                # asyncpg не понимает postgresql+asyncpg://
                if url.startswith("postgresql+asyncpg://"):
                    url = url.replace("postgresql+asyncpg://", "postgresql://", 1)

                # Если search_path не передан, берём из SCHEMA_MAP
                if search_path is None:
                    from src.core.db_config import get_search_path
                    search_path = get_search_path(alias)

                pool = await asyncpg.create_pool(
                    url,
                    min_size=min_size,
                    max_size=max_size,
                    server_settings={
                        "statement_timeout": "30000",  # 30 секунд
                        "application_name": f"app_{alias}",
                        "search_path": search_path,
                    },
                    command_timeout=30,
                )

                self._pools[alias] = pool
                logger.info(f"[DB_MANAGER] Пул '{alias}' создан, search_path={search_path}")
                return pool

            except Exception as e:
                logger.error(f"[DB_MANAGER] Ошибка создания пула '{alias}': {e}", exc_info=True)
                raise RuntimeError(f"Не удалось инициализировать пул '{alias}': {e}") from e

    async def get_pool(self, alias: str) -> asyncpg.Pool:
        """
        Получение пула по алиасу (с авто-инициализацией при необходимости).

        Args:
            alias: Алиас БД

        Returns:
            asyncpg.Pool: Пул соединений

        Raises:
            ValueError: Если алиас не зарегистрирован
        """
        if alias not in self._pools:
            await self.init_pool(alias)
        return self._pools[alias]

    async def fetch_all(
            self,
            alias: str,
            query: str,
            *params: Any,
            normalize_types: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Выполнение SELECT-запроса с возвратом списка словарей.

        Args:
            alias: Алиас БД
            query: SQL-запрос с параметрами ($1, $2, ...)
            *params: Параметры запроса
            normalize_types: Если True — нормализовать типы через SchemaComparator

        Returns:
            List[Dict[str, Any]]: Список строк как словарей

        Example:
            rows = await db.fetch_all(
                "app_ecomru",
                "SELECT * FROM users WHERE age > $1",
                18
            )
        """
        pool = await self.get_pool(alias)
        async with pool.acquire() as conn:
            records = await conn.fetch(query, *params)

            if not records:
                return []

            if normalize_types:
                comparator = self._get_comparator()
                return [comparator.normalize_record(dict(row)) for row in records]

            return [dict(row) for row in records]

    async def fetch_one(
            self,
            alias: str,
            query: str,
            *params: Any,
            normalize_types: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Выполнение SELECT-запроса с возвратом одной записи или None.

        Args:
            alias: Алиас БД
            query: SQL-запрос с параметрами ($1, $2, ...)
            *params: Параметры запроса
            normalize_types: Если True — нормализовать типы

        Returns:
            Dict[str, Any] | None: Первая запись или None если пусто

        Example:
            user = await db.fetch_one(
                "app_users",
                "SELECT * FROM users WHERE email = $1",
                "test@example.com"
            )
        """
        pool = await self.get_pool(alias)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)

            if row is None:
                return None

            result = dict(row)

            if normalize_types:
                comparator = self._get_comparator()
                return comparator.normalize_record(result)

            return result

    async def fetch_val(
            self,
            alias: str,
            query: str,
            *params: Any,
            column: int = 0
    ) -> Optional[Any]:
        """
        Получение одного значения из первой колонки первой строки.

        Args:
            alias: Алиас БД
            query: SQL-запрос с параметрами
            *params: Параметры запроса
            column: Индекс колонки для возврата (по умолчанию 0)

        Returns:
            Any: Значение или None

        Example:
            count = await db.fetch_val(
                "app_mail",
                "SELECT COUNT(*) FROM mail_tasks WHERE status = $1",
                "pending"
            )
        """
        pool = await self.get_pool(alias)
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *params, column=column)

    async def execute(
            self,
            alias: str,
            query: str,
            *params: Any
    ) -> str:
        """
        Выполнение команды без возврата данных (INSERT/UPDATE/DELETE).

        Args:
            alias: Алиас БД
            query: SQL-запрос с параметрами
            *params: Параметры запроса

        Returns:
            str: Статус команды (напр. "INSERT 0 1")

        Example:
            status = await db.execute(
                "app_ecomru",
                "UPDATE users SET last_login = NOW() WHERE id = $1",
                user_id
            )
        """
        pool = await self.get_pool(alias)
        async with pool.acquire() as conn:
            return await conn.execute(query, *params)

    async def execute_many(
            self,
            alias: str,
            query: str,
            records: List[tuple]
    ) -> None:
        """
        Пакетное выполнение запроса с множеством записей.

        Args:
            alias: Алиас БД
            query: SQL-запрос с параметрами
            records: Список кортежей параметров

        Example:
            await db.execute_many(
                "app_mail",
                "INSERT INTO mail_tasks (to_email, subject) VALUES ($1, $2)",
                [
                    ("user1@example.com", "Hello"),
                    ("user2@example.com", "World"),
                ]
            )
        """
        pool = await self.get_pool(alias)
        async with pool.acquire() as conn:
            await conn.executemany(query, records)

    @asynccontextmanager
    async def transaction(
            self,
            alias: str,
            isolation: str = "read_committed"
    ) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Контекстный менеджер для безопасной транзакции.

        Args:
            alias: Алиас БД
            isolation: Уровень изоляции:
                'read_committed' | 'repeatable_read' | 'serializable'

        Yields:
            asyncpg.Connection: Соединение в контексте транзакции

        Example:
            async with db.transaction("app_data_registry") as conn:
                await conn.execute("INSERT INTO ...")
                # При ошибке — автоматический ROLLBACK
        """
        pool = await self.get_pool(alias)
        async with pool.acquire() as conn:
            try:
                async with conn.transaction(isolation=isolation):
                    yield conn
            except Exception as e:
                logger.error(f"[DB_MANAGER] Транзакция '{alias}' отменена: {type(e).__name__}: {e}")
                raise

    async def ping(self, alias: str) -> bool:
        """
        Проверка доступности БД по алиасу.

        Args:
            alias: Алиас БД

        Returns:
            bool: True если подключение успешно

        Example:
            if await db.ping("app_ecomru"):
                logger.info("БД доступна")
        """
        try:
            pool = await self.get_pool(alias)
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.warning(f"[DB_MANAGER] Ping '{alias}' failed: {e}")
            return False

    async def close_pool(self, alias: str) -> bool:
        """
        Закрытие пула ТОЛЬКО для указанного алиаса.
        Критично для изолированного shutdown приложений!

        Args:
            alias: Алиас БД для закрытия

        Returns:
            bool: True если пул был закрыт

        Example:
            await db.close_pool("app_ecomru")
        """
        if alias not in self._pools:
            logger.debug(f"[DB_MANAGER] Пул '{alias}' не найден для закрытия")
            return False

        try:
            pool = self._pools.pop(alias)
            if not pool.is_closed():
                await pool.close()
            logger.info(f"[DB_MANAGER] Пул '{alias}' закрыт")
            return True
        except Exception as e:
            logger.error(f"[DB_MANAGER] Ошибка закрытия пула '{alias}': {e}")
            return False

    async def close_all(self) -> None:
        """
        Закрытие ВСЕХ пулов (только для главного процесса!).
        Не использовать в изолированных приложениях!

        Example:
            # В главном main.py при shutdown
            await db.close_all()
        """
        aliases = list(self._pools.keys())
        for alias in aliases:
            await self.close_pool(alias)
        logger.info("[DB_MANAGER] Все пулы закрыты")

    def get_pool_info(self, alias: str) -> Optional[Dict[str, Any]]:
        """
        Получение статистики пула (для мониторинга/отладки).

        Args:
            alias: Алиас БД

        Returns:
            Dict с размерами пула или None если не инициализирован

        Example:
            info = db.get_pool_info("app_ecomru")
            print(f"Pool size: {info['current_size']}/{info['max_size']}")
        """
        if alias not in self._pools:
            return None

        pool = self._pools[alias]
        return {
            "alias": alias,
            "min_size": pool.get_min_size(),
            "max_size": pool.get_max_size(),
            "current_size": pool.get_size(),
            "idle_size": pool.get_idle_size(),
            "is_closed": pool.is_closed()
        }

    # --- Синхронный фоллбэк для legacy / миграций / background ---

    @contextmanager
    def get_sync_cursor(self, alias: str):
        """
        Прямое psycopg2 подключение (только для фоновых задач/миграций).
        НЕ использовать в асинхронных роутах!

        Args:
            alias: Алиас БД

        Yields:
            psycopg2.extensions.cursor: Синхронный курсор

        Example:
            with db.get_sync_cursor("app_ecomru") as cur:
                cur.execute("SELECT * FROM users")
                rows = cur.fetchall()
        """
        secure_dsn = DBConfig.get_dsn(alias)
        dsn = secure_dsn.raw.replace("postgresql+asyncpg://", "postgresql://", 1)

        conn = None
        try:
            conn = psycopg2.connect(dsn)
            with conn.cursor() as cur:
                yield cur
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"[DB_MANAGER] Ошибка sync-транзакции '{alias}': {e}")
            raise
        finally:
            if conn:
                conn.close()

    def __del__(self):
        """Гарантированная очистка при уничтожении (на всякий случай)."""
        # Не блокируем в __del__, просто логируем если пулы ещё есть
        if self._pools:
            logger.warning(f"[DB_MANAGER] Уничтожение с активными пулами: {list(self._pools.keys())}")


# Экспорт для импорта
__all__ = ["DBManager"]