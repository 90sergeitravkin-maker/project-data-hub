# src/back/app_datasets/services.py
"""
Единый сервис для работы с dim_data_sets_verified.
Все CRUD-операции + сканирование файлов.
"""

import re
import json
import asyncio
import datetime
import duckdb
import hashlib

from pathlib import Path
from typing import Union, List, Generator, Dict, Optional, Any

from fastapi import HTTPException, status
from sqlalchemy import update, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from src.core.logger import logger
from src.database.manager import DBManager
from src.back.app_datasets.config import DATA_FILE_EXT, DB_ALIAS, CONFIG_PATH
from src.back.app_datasets.models import DataSetsVerified
from src.back.app_datasets.schemas import (
    DataSetCreate,
    DataSetUpdate,
    DataSetResponse,
    DataSetAggregateResponse,
)


class DataSetsVerifiedServices:
    """
    Единый сервис для dim_data_sets_verified.
    CRUD + сканирование файлов.
    """

    # ==================== CRUD ====================

    @staticmethod
    async def create(session: AsyncSession, data: DataSetCreate) -> DataSetResponse:
        """Создание записи через ORM."""
        hash_sum = getattr(data, "hash_sum", None)
        if not hash_sum:
            hash_sum = hashlib.sha256(
                f"{data.name}:{data.period}:{data.link}".encode()
            ).hexdigest()

        db_dataset = DataSetsVerified(
            hash_sum=hash_sum,
            name=data.name,
            period=data.period,
            link=data.link,
            validation=data.validation,
        )
        session.add(db_dataset)
        await session.commit()
        await session.refresh(db_dataset)
        return DataSetResponse.model_validate(db_dataset)

    @staticmethod
    async def get_by_id(session: AsyncSession, dataset_id: int) -> DataSetResponse:
        """Получение записи по ID."""
        result = await session.execute(
            select(DataSetsVerified).where(DataSetsVerified.id == dataset_id)
        )
        db_dataset = result.scalar_one_or_none()
        if not db_dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись не найдена",
            )
        return DataSetResponse.model_validate(db_dataset)

    @staticmethod
    async def get_all(
            session: AsyncSession, skip: int = 0, limit: int = 100
    ) -> list[DataSetResponse]:
        """Список записей с пагинацией."""
        result = await session.execute(
            select(DataSetsVerified).offset(skip).limit(limit)
        )
        return [DataSetResponse.model_validate(ds) for ds in result.scalars().all()]

    @staticmethod
    async def update(
            session: AsyncSession, hash_sum: str, data: DataSetUpdate
    ) -> DataSetResponse:
        """Частичное обновление записи по hash_sum."""
        result = await session.execute(
            select(DataSetsVerified).where(DataSetsVerified.hash_sum == hash_sum)
        )
        db_dataset = result.scalar_one_or_none()
        if not db_dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись не найдена",
            )

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return DataSetResponse.model_validate(db_dataset)

        await session.execute(
            update(DataSetsVerified)
            .where(DataSetsVerified.hash_sum == hash_sum)
            .values(**update_data)
        )
        await session.commit()

        result = await session.execute(
            select(DataSetsVerified).where(DataSetsVerified.hash_sum == hash_sum)
        )
        return DataSetResponse.model_validate(result.scalar_one())

    @staticmethod
    async def aggregate_by_name(
            session: AsyncSession,
            name_filter: str,
            skip: int = 0,
            limit: int = 100,
    ) -> list[DataSetAggregateResponse]:
        """Агрегация данных по name и period."""
        query = text("""
            WITH bt AS (
                SELECT
                    name                                                   AS "name",
                    period                                                 AS "period",
                    COALESCE((validation::jsonb ->> 'file_size')::bigint, 0) AS "size",
                    COALESCE((validation::jsonb ->> 'row_count')::bigint, 0) AS "rows"
                FROM app_datasets.dim_data_sets_verified
                WHERE 1=1
                  AND name = :name_filter
                  AND validation IS NOT NULL
                  AND is_active = TRUE
            )
            SELECT
                name        AS name,
                period      AS period,
                SUM("size") AS size,
                SUM("rows") AS rows
            FROM bt
            GROUP BY name, period
            ORDER BY name, period
            OFFSET :skip LIMIT :limit
        """)
        result = await session.execute(
            query, {"name_filter": name_filter, "skip": skip, "limit": limit}
        )
        return [
            DataSetAggregateResponse(
                name=row.name, period=row.period, size=row.size, rows=row.rows
            )
            for row in result.all()
        ]

    # ==================== Сканирование файлов ====================

    path_raw = DATA_FILE_EXT

    @staticmethod
    def _get_all_file(
            folder_path: Union[str, Path] = None,
            extensions: Union[str, List[str]] = "*",
    ) -> Generator[Path, None, None]:
        path = Path(folder_path or DataSetsVerifiedServices.path_raw)
        if not path.exists():
            raise FileNotFoundError(f"Директория не найдена: {folder_path}")
        if isinstance(extensions, str) and extensions == "*":
            for file_path in path.rglob("**/*"):
                if file_path.is_file():
                    yield file_path
            return
        ext_list = (
            [ext.strip().lower() for ext in extensions.split(",")]
            if isinstance(extensions, str)
            else [ext.lower() for ext in extensions]
        )
        ext_list = [f".{ext}" if not ext.startswith(".") else ext for ext in ext_list]
        for file_path in path.rglob("**/*"):
            if file_path.is_file() and file_path.suffix.lower() in ext_list:
                yield file_path

    @staticmethod
    def _get_hash_file(file_path: Union[str, Path], algorithm: str = "sha256") -> str:
        with open(file_path, "rb") as f:
            return hashlib.file_digest(f, algorithm).hexdigest()

    @staticmethod
    def _extract_metadata(file_path: Union[str, Path]) -> Dict[str, Optional[Any]]:
        path = Path(file_path)
        parts = list(path.parts)
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        date_index = next(
            (i for i, part in enumerate(parts) if date_pattern.match(part)), None
        )
        if date_index is None:
            return {"source": None, "period": None, "date": None}
        source = parts[date_index - 1] if date_index > 0 else None
        period = None
        if date_index + 1 < len(parts):
            next_part = parts[date_index + 1]
            if re.match(r"^\d{4}$|^\d{6}$|^\d{8}$", next_part):
                period = next_part
        try:
            date_obj = datetime.datetime.strptime(parts[date_index], "%Y-%m-%d").date()
        except ValueError:
            date_obj = None
        return {"source": source, "period": period, "date": date_obj}

    @staticmethod
    def _get_file_size(file_path: Union[str, Path]) -> int:
        return Path(file_path).stat().st_size

    @staticmethod
    def _get_row_count(file_path: Union[str, Path]) -> int:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Файл не найден: {path}")
        safe_path = path.as_posix().replace("'", "''")
        suffixes = path.suffixes
        match suffixes:
            case _ if ".parquet" in suffixes:
                query = f"SELECT COUNT(*) FROM read_parquet('{safe_path}')"
            case _ if ".json" in suffixes:
                query = f"SELECT COUNT(*) FROM read_json_auto('{safe_path}')"
            case _ if ".csv" in suffixes:
                query = f"SELECT COUNT(*) FROM read_csv_auto('{safe_path}')"
            case _:
                return 0
        with duckdb.connect() as conn:
            return conn.execute(query).fetchone()[0]

    @classmethod
    async def _save_result(cls, result: dict, error: Optional[str] = None) -> None:
        error_location = "src/back/app_datasets, services.py, метод _save_result"
        db_manager = DBManager()
        validation_json = json.dumps(result.get("validation")) if result.get("validation") else None
        upload_date = result.get("upload_date")
        if isinstance(upload_date, str):
            try:
                upload_date = datetime.datetime.strptime(upload_date, "%Y-%m-%d").date()
            except ValueError:
                try:
                    upload_date = datetime.datetime.fromisoformat(upload_date).date()
                except ValueError:
                    upload_date = None
        query = """
            INSERT INTO app_datasets.dim_data_sets_verified
                (hash_sum, name, period, date_created, link, validation, is_active)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
            ON CONFLICT (hash_sum) DO UPDATE SET
                 name         = EXCLUDED.name
                ,period       = EXCLUDED.period
                ,date_created = EXCLUDED.date_created
                ,link         = EXCLUDED.link
                ,validation   = EXCLUDED.validation
                ,is_active    = EXCLUDED.is_active
        """
        params = (
            result.get("hash_sum"),
            result.get("name"),
            result.get("period"),
            upload_date,
            result.get("link"),
            validation_json,
            result.get("is_active", True),
        )
        try:
            await db_manager.execute(DB_ALIAS, query, *params)
            logger.debug(f"Сохранена запись для файла {result.get('link', 'unknown')}")
        except Exception as e:
            logger.error(f"Ошибка сохранения записи {result.get('hash_sum')}: {e} | {error_location}")
            raise

    @classmethod
    def _load_source_fields_config(
            cls, config_path: Optional[Path] = None
    ) -> Dict[str, List[str]]:
        if config_path is None:
            config_path = CONFIG_PATH
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger.info(f"Загружен конфиг полей источников: {config}")
            return config
        except Exception as e:
            logger.warning(
                f"Не удалось загрузить конфиг полей источников из {config_path}: {e}"
            )
            return {}

    @staticmethod
    def _get_distinct_values(
            file_path: Union[str, Path], field: str
    ) -> Optional[List[Any]]:
        path = Path(file_path)
        if not path.is_file():
            return None
        safe_path = path.as_posix().replace("'", "''")
        suffixes = path.suffixes
        if ".parquet" in suffixes:
            table_expr = f"read_parquet('{safe_path}')"
        elif ".json" in suffixes:
            table_expr = f"read_json_auto('{safe_path}')"
        elif ".csv" in suffixes:
            table_expr = f"read_csv_auto('{safe_path}')"
        else:
            return None
        field_escaped = f'"{field}"'
        query = f"SELECT DISTINCT {field_escaped} FROM {table_expr}"
        try:
            with duckdb.connect() as conn:
                result = conn.execute(query).fetchall()
                return [row[0] for row in result]
        except Exception as e:
            logger.debug(
                f"Не удалось получить уникальные значения для поля {field} из {file_path}: {e}"
            )
            return None

    @classmethod
    async def scan_and_save(cls) -> None:
        """Сканирование папки и сохранение метаданных."""
        raw_path = Path(cls.path_raw)
        if not raw_path.exists():
            raise FileNotFoundError(f"Директория не найдена: {raw_path}")
        loop = asyncio.get_running_loop()
        files = await loop.run_in_executor(None, list, cls._get_all_file())
        source_config = cls._load_source_fields_config()
        for i_file in files:
            result = {
                "hash_sum": None,
                "name": None,
                "period": None,
                "upload_date": None,
                "link": str(i_file),
                "validation": {},
                "is_active": True,
            }
            error = None
            try:
                metadata = await loop.run_in_executor(None, cls._extract_metadata, i_file)
                result["name"] = metadata.get("source")
                result["period"] = metadata.get("period")
                result["upload_date"] = metadata.get("date")
                try:
                    result["hash_sum"] = await loop.run_in_executor(
                        None, cls._get_hash_file, i_file
                    )
                except Exception as e:
                    result["hash_sum"] = hashlib.sha256(str(i_file).encode()).hexdigest()
                    error = f"Ошибка вычисления хеша: {e}"
                result["validation"]["file_size"] = await loop.run_in_executor(
                    None, cls._get_file_size, i_file
                )
                try:
                    row_count = await loop.run_in_executor(
                        None, cls._get_row_count, i_file
                    )
                    result["validation"]["row_count"] = row_count
                except Exception as e:
                    result["validation"]["row_count"] = None
                    if not error:
                        error = f"Ошибка подсчёта строк: {e}"
                source = metadata.get("source")
                if source and source_config:
                    fields = source_config.get(source, [])
                    if fields:
                        logger.debug(f"Для источника {source} обрабатываются поля: {fields}")
                        distinct_values = {}
                        for field in fields:
                            try:
                                values = await loop.run_in_executor(
                                    None, cls._get_distinct_values, i_file, field
                                )
                                if values is not None:
                                    distinct_values[field] = values
                            except Exception as e:
                                logger.debug(
                                    f"Ошибка получения уникальных значений для поля {field}: {e}"
                                )
                        if distinct_values:
                            result["validation"]["distinct_values"] = distinct_values
            except Exception as e:
                error = str(e)
                if not result["hash_sum"]:
                    result["hash_sum"] = hashlib.sha256(str(i_file).encode()).hexdigest()
            await cls._save_result(result, error=error)

    @classmethod
    async def check_and_update_missing_files(
            cls, batch_size: int = 1
    ) -> Dict[str, int]:
        """Проверка наличия файлов для активных записей."""
        db_manager = DBManager()
        total_checked = 0
        total_missing = 0
        total_updated = 0
        last_hash = ""
        while True:
            select_query = """
                SELECT hash_sum, link
                FROM app_datasets.dim_data_sets_verified
                WHERE is_active = true AND hash_sum > $1
                ORDER BY hash_sum
                LIMIT $2
            """
            rows = await db_manager.fetch_all(DB_ALIAS, select_query, last_hash, batch_size)
            if not rows:
                break
            missing_hashes = []
            for row in rows:
                total_checked += 1
                file_path = Path(row["link"])
                if not file_path.exists():
                    missing_hashes.append(row["hash_sum"])
                last_hash = row["hash_sum"]
            if missing_hashes:
                total_missing += len(missing_hashes)
                placeholders = ",".join(
                    [f"${i + 1}" for i in range(len(missing_hashes))]
                )
                update_query = f"""
                    UPDATE app_datasets.dim_data_sets_verified
                    SET is_active = false
                    WHERE hash_sum IN ({placeholders})
                """
                await db_manager.execute(DB_ALIAS, update_query, *missing_hashes)
                total_updated += len(missing_hashes)
            if len(rows) < batch_size:
                break
        logger.info(
            f"Проверка активных файлов завершена. Проверено: {total_checked}, "
            f"отсутствует: {total_missing}, обновлено: {total_updated}"
        )
        return {
            "checked": total_checked,
            "missing": total_missing,
            "updated": total_updated,
        }

    @classmethod
    async def save_file_metadata(
            cls,
            file_path: Path,
            entity: Optional[str] = None,
            period: Optional[str] = None,
            updated_at: Optional[str] = None,
    ) -> None:
        """Сохраняет информацию об одном файле (используется app_ecomru)."""
        loop = asyncio.get_running_loop()
        try:
            hash_sum = await loop.run_in_executor(None, cls._get_hash_file, file_path)
        except Exception as e:
            hash_sum = hashlib.sha256(str(file_path).encode()).hexdigest()
            logger.warning(
                f"[DATASETS] Ошибка вычисления хеша для {file_path}: {e}, используем fallback"
            )
        if entity is None or period is None or updated_at is None:
            metadata = await loop.run_in_executor(None, cls._extract_metadata, file_path)
            entity = entity or metadata.get("source")
            period = period or metadata.get("period")
            if updated_at is None and metadata.get("date") is not None:
                updated_at = metadata["date"]
        if isinstance(updated_at, str):
            try:
                updated_at = datetime.datetime.strptime(updated_at, "%Y-%m-%d").date()
            except ValueError:
                try:
                    updated_at = datetime.datetime.fromisoformat(updated_at).date()
                except ValueError:
                    updated_at = None
        size = await loop.run_in_executor(None, cls._get_file_size, file_path)
        try:
            row_count = await loop.run_in_executor(None, cls._get_row_count, file_path)
        except Exception:
            row_count = None
        result = {
            "hash_sum": hash_sum,
            "name": entity,
            "period": period,
            "upload_date": updated_at,
            "link": str(file_path),
            "validation": {"file_size": size, "row_count": row_count},
            "is_active": True,
        }
        await cls._save_result(result, error=None)
