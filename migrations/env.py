import asyncio
import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# 1. Добавляем корень проекта в sys.path ДО любых импортов из src
PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 2. Импорты из проекта
from src.database.base import Base
from src.core.db_config import to_asyncpg_url, SCHEMA_MAP

# 3. Явный импорт всех моделей, чтобы Base.metadata увидел их таблицы
from src.back.app_datasets.models import DataSetsVerified
from src.back.app_data_registry.models import DataSource, Service, ServiceVersion, ServiceVersionDataSource
from src.back.app_ecomru.models import NotificationLog, ProcessingGroup, GroupFile, DownloadedFile
from src.back.app_file_manager.models import FileDownloadLog, SchemaExtractionLog
from src.back.app_link.models import Link
from src.back.app_mail.models import MailTask
from src.back.app_monitor.models import MemorySnapshot, RequestMemoryStat, MemoryAlert
from src.back.app_text_dup_check.models import TextEntry
from src.back.app_users.models import (
    AuthUser, LoginStat, AuthRefreshToken,
    AuthRole, AuthUserRole, AuthEmailToken, AuthRateLimit
)

# ============================================================================
# НАСТРОЙКА ALEMBIC
# ============================================================================

config = context.config

# Настройка логирования из alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Получаем URL через централизованный конфиг (алиас "base_01" -> DB_LOCAL_01)
try:
    db_url = to_asyncpg_url("base_01")
except ValueError as e:
    raise ValueError(f"Не удалось получить DSN для миграций: {e}")

db_url = db_url.replace("%", "%%")# если в пароле есть % то их требуется экранировать

config.set_main_option("sqlalchemy.url", db_url)


# Metadata для autogenerate
target_metadata = Base.metadata

# ============================================================================
# ФИЛЬТРАЦИЯ СХЕМ (Критично для include_schemas=True)
# ============================================================================

# Собираем все схемы, которые использует проект, из SCHEMA_MAP
ALLOWED_SCHEMAS = {'public'}
for search_path in SCHEMA_MAP.values():
    for schema in search_path.split(','):
        ALLOWED_SCHEMAS.add(schema.strip())


def include_name(name, type_, parent_names):
    """
    Фильтр для Alembic: игнорируем системные схемы PostgreSQL.
    Без этого autogenerate попытается удалить таблицы из information_schema.
    """
    if type_ == "schema":
        return name in ALLOWED_SCHEMAS
    return True


# ============================================================================
# РЕЖИМЫ ВЫПОЛНЕНИЯ
# ============================================================================

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        version_table_schema='public',  # Таблица alembic_version всегда в public
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        version_table_schema='public',
        compare_type=False,  # ❗️ Рекомендую False. Иначе Alembic будет спамить ALTER COLUMN из-за разницы VARCHAR/TEXT
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context."""

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
