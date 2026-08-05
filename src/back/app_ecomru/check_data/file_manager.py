#  src/back/app_ecomru/check_data/file_manager.py
import os
import shutil
import duckdb

from pathlib import Path
from typing import Union, List, Dict, Any, Optional, Generator

from core.logger import logger
from src.back.app_ecomru.config import DATA_FILE_RAW, DATA_FILE_TEMP, MAX_FILE_SIZE


class DuckDBFileManager:
    """
    Класс для работы с файлами (Parquet, CSV, JSON) с использованием DuckDB.
    Предоставляет полный набор методов для проверки, разбиения, конвертации,
    поиска файлов, работы с путями и контрольными суммами.
    """
    memory_limit = '2GB'

    def __init__(self, raw_dir: Optional[Path] = None, test_dir: Optional[Path] = None,
                 max_file_size: Optional[int] = None):
        """
        Инициализация менеджера.

        :param raw_dir: Корневая директория с исходными данными (если None – используется DATA_FILE_RAW)
        :param test_dir: Корневая директория для результатов (если None – используется DATA_FILE_TEMP)
        :param max_file_size: Максимальный размер файла при разбиении (если None – используется MAX_FILE_SIZE)
        """
        self.raw_dir = Path(raw_dir) if raw_dir else DATA_FILE_RAW
        self.test_dir = Path(test_dir) if test_dir else DATA_FILE_TEMP
        self.max_file_size = max_file_size if max_file_size is not None else MAX_FILE_SIZE

    # ---------- Вспомогательные методы работы с папками ----------

    @staticmethod
    def clear_directory(directory: Path) -> None:
        """
        Очищает содержимое указанной папки, не удаляя саму папку.
        Если папка не существует, ничего не делает.
        """
        if not directory.exists():
            return
        for item in directory.iterdir():
            if item.is_file():
                item.unlink()
            else:
                shutil.rmtree(item)

    @staticmethod
    def build_path(base: Union[str, Path], *parts: Optional[str]) -> Path:
        """
        Собирает путь из базовой части и компонентов, пропуская None и пустые строки.
        """
        path = Path(base)
        for part in parts:
            if part is not None and str(part).strip():
                path /= part
        return path

    @staticmethod
    def get_all_files(folder_path: Union[str, Path],
                      extensions: Union[str, List[str]] = '*') -> Generator[Path, None, None]:
        """
        Рекурсивно перебирает файлы в папке, фильтруя по расширениям.

        :param folder_path: Путь к папке
        :param extensions: Строка с расширениями через запятую, список или '*' для всех
        :return: Генератор объектов Path
        """
        root = Path(folder_path)

        if isinstance(extensions, str):
            if extensions == '*':
                for f in root.rglob('*'):
                    if f.is_file():
                        yield f
                return
            ext_list = [ext.strip().lower() for ext in extensions.split(',')]
        else:
            ext_list = [ext.lower() for ext in extensions]

        ext_list = [f'.{ext}' if not ext.startswith('.') else ext for ext in ext_list]

        for f in root.rglob('*'):
            if f.is_file() and f.suffix.lower() in ext_list:
                yield f

    @staticmethod
    def get_folders_with_files(root_path: Union[str, Path],
                               extensions: Union[str, List[str]] = '*') -> List[Path]:
        """
        Возвращает список папок, содержащих файлы с указанными расширениями.
        """
        root = Path(root_path)
        found = set()

        if isinstance(extensions, str):
            if extensions == '*':
                patterns = ['*.*']
            else:
                patterns = [f'*.{ext.strip()}' for ext in extensions.split(',')]
        else:
            patterns = [f'*.{ext}' for ext in extensions]

        for pattern in patterns:
            for file_path in root.rglob(pattern):
                if file_path.is_file():
                    found.add(file_path.parent)

        return sorted(found)

    @staticmethod
    def remove_suffix_from_files(directory: str, extension: str, suffix: str = '.sended') -> None:
        """
        Рекурсивно переименовывает файлы, убирая суффикс (например, .sended) из имени.
        """
        logger.debug(f'Removing suffix "{suffix}" from {extension} files in {directory}')
        renamed_count = 0

        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(f'.{extension}{suffix}'):
                    old_path = os.path.join(root, file)
                    new_path = os.path.join(root, file.removesuffix(suffix))

                    if os.path.exists(new_path):
                        logger.warning(f'Target file already exists, skipping: {new_path}')
                        continue

                    try:
                        os.rename(old_path, new_path)
                        logger.info(f'Renamed: {os.path.basename(old_path)} -> {os.path.basename(new_path)}')
                        renamed_count += 1
                    except OSError as e:
                        logger.error(f'Failed to rename {old_path}: {e}')

        logger.info(f'Total renamed files: {renamed_count}')

    # ---------- Методы работы с путями ----------

    @staticmethod
    def trim_to_source(full_path: str) -> str:
        """
        Обрезает путь до части после последнего вхождения 'source'.
        """
        marker = 'source'
        index = full_path.find(marker)
        if index == -1:
            raise ValueError(f"Подстрока '{marker}' не найдена в пути: {full_path}")
        remainder = full_path[index + len(marker):]
        if remainder.startswith(('\\', '/')):
            remainder = remainder[1:]
        return remainder

    @staticmethod
    def get_relative_path(full_path: str, base_directory: str) -> str:
        """
        Возвращает относительный путь файла относительно базовой директории.
        """
        full_path_obj = Path(full_path).resolve()
        base_dir_obj = Path(base_directory).resolve()

        if not full_path_obj.exists():
            raise FileNotFoundError(f"Файл не найден: {full_path}")

        try:
            return str(full_path_obj.relative_to(base_dir_obj))
        except ValueError as e:
            raise ValueError(f"Путь {full_path} не находится внутри {base_directory}") from e

    @staticmethod
    def sanitize_name(value: str) -> str:
        """Заменяет недопустимые символы в имени файла."""
        return str(value).replace('/', '_').replace('\\', '_').replace(':', '_') \
            .replace('*', '_').replace('?', '_').replace('"', '_') \
            .replace('<', '_').replace('>', '_').replace('|', '_')

    # ---------- Проверка и анализ файлов ----------

    def comprehensive_file_check(self, filepath: str) -> Optional[List[tuple]]:
        """
        Проверяет файл: существование, расширение, возможность прочитать через DuckDB.
        Возвращает схему (результат DESCRIBE) или None при ошибке.
        """
        filepath = str(filepath)
        if not os.path.isfile(filepath):
            logger.warning(f'Файл не найден: {filepath}')
            return None

        ext = os.path.splitext(filepath)[1].lower()
        readers = {
            '.parquet': "read_parquet",
            '.csv': "read_csv",
            '.json': "read_json",
        }

        if ext not in readers:
            logger.warning(f"Неподдерживаемый формат: {ext}")
            return None

        try:
            with duckdb.connect() as con:
                query = f"DESCRIBE FROM {readers[ext]}(?)"
                result = con.execute(query, [filepath]).fetchall()
            return result
        except Exception as e:
            logger.exception(f"Ошибка при выполнении DESCRIBE для {filepath}: {e}")
            return None

    # ---------- Контрольные суммы Comtrade ----------
    def get_comtrade_checksum_control(self, path_pattern: Union[str, Path]) -> Dict[str, Dict[str, Any]]:
        """
        Вычисляет контрольные суммы для всех Parquet-файлов, соответствующих шаблону.
        Возвращает словарь {checksum: {"control_sum": ..., "count_row": количество_строк_для_этого_checksum}}.

        :param path_pattern: путь к папке, файлу или маске (например, "/data/*.parquet")
        """
        pattern = Path(path_pattern)
        if pattern.is_dir():
            files = list(pattern.glob("*.parquet"))
        elif pattern.is_file() and pattern.suffix == '.parquet':
            files = [pattern]
        else:
            parent = pattern.parent
            if parent.exists():
                files = list(parent.glob(pattern.name))
            else:
                files = []

        if not files:
            logger.warning(f"Нет Parquet-файлов по шаблону: {path_pattern}")
            return {}

        files_str = ", ".join([f"'{f.as_posix()}'" for f in files])

        with duckdb.connect() as con:
            try:
                # Получаем для каждого dataset_checksum: контрольную сумму и количество строк
                sql = f"""
                    SELECT
                        dataset_checksum
                        ,ROUND(
                              COALESCE(ABS(1 - COALESCE(SUM(CASE WHEN aggr_level = 0 THEN primary_value END), 0) / NULLIF(COALESCE(SUM(CASE WHEN aggr_level = 2 THEN primary_value END), 0), 0)), 0)
                            + COALESCE(ABS(1 - COALESCE(SUM(CASE WHEN aggr_level = 0 THEN primary_value END), 0) / NULLIF(COALESCE(SUM(CASE WHEN aggr_level = 4 THEN primary_value END), 0), 0)), 0)
                            + COALESCE(ABS(1 - COALESCE(SUM(CASE WHEN aggr_level = 0 THEN primary_value END), 0) / NULLIF(COALESCE(SUM(CASE WHEN aggr_level = 6 THEN primary_value END), 0), 0)), 0)
                        , 5) AS control_sum
                        ,COUNT(*) AS row_count
                    FROM read_parquet([{files_str}])
                    WHERE customs_code = 'C00'
                      AND mos_code = 0
                      AND mot_code = 0
                      AND partner2_code = 0
                      AND partner_code != 0
                    GROUP BY dataset_checksum
                """
                result = {}
                for checksum, control_sum, row_count in con.execute(sql).fetchall():
                    result[checksum] = {
                        "control_sum": control_sum,
                        "count_row": row_count
                    }
                logger.debug(f"result={result}")
                return result
            except Exception as e:
                logger.error(f"Ошибка при вычислении контрольной суммы: {e}")
                return {}

    # ---------- Разбиение данных по столбцу ----------

    def split_data_by_columns(self, source_dir: Path, target_dir: Path,
                              split_column: str) -> Dict[str, Any]:
        """
        Разбивает данные из Parquet-файлов в source_dir на отдельные файлы по уникальным
        значениям столбца split_column. Результаты сохраняются в target_dir.
        Использует параметр self.max_file_size для управления размером частей.

        :param source_dir: Папка с исходными Parquet-файлами
        :param target_dir: Папка для сохранения результатов
        :param split_column: Имя столбца для разбиения
        :return: Словарь со статусом и статистикой
        """
        source_dir = Path(source_dir)
        target_dir = Path(target_dir)

        if not source_dir.exists():
            return {"status": "error", "error": f"Исходная директория не найдена: {source_dir}"}

        files = [f.as_posix() for f in source_dir.glob("*.parquet")]
        if not files:
            return {"status": "empty", "files_found": 0, "message": "Нет .parquet файлов"}

        # Очищаем целевую папку
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        with duckdb.connect() as con:
            con.execute(f"SET memory_limit='{self.memory_limit}'")
            con.execute("SET threads TO 4")

            files_str = ", ".join([f"'{f}'" for f in files])
            safe_column = split_column.replace('"', '""')

            unique_values = con.execute(f"""
                SELECT DISTINCT "{safe_column}"
                FROM read_parquet([{files_str}])
                WHERE "{safe_column}" IS NOT NULL
                  AND TRIM("{safe_column}"::VARCHAR) != ''
            """).fetchall()

            result_stats = {}
            total_rows_all = 0

            for (value,) in unique_values:
                base_name = self.sanitize_name(str(value))
                escaped_value = str(value).replace("'", "''")

                pattern = f"{base_name}_{{i}}.parquet"
                copy_sql = f"""
                    COPY (
                        FROM read_parquet([{files_str}])
                        WHERE "{safe_column}" = '{escaped_value}'
                    )
                    TO '{target_dir.as_posix()}/'
                    (FORMAT PARQUET,
                     CODEC 'ZSTD',
                     FILE_SIZE_BYTES {self.max_file_size},
                     FILENAME_PATTERN '{pattern}',
                     OVERWRITE_OR_IGNORE true)
                """
                con.execute(copy_sql)

                part_files = sorted(target_dir.glob(f"{base_name}_*.parquet"))
                if not part_files:
                    continue

                renamed_paths = []
                for idx, old_path in enumerate(part_files, start=1):
                    new_name = f"{base_name}_{idx:03d}.parquet"
                    new_path = old_path.parent / new_name
                    old_path.rename(new_path)
                    renamed_paths.append(new_path.as_posix())

                files_list = ", ".join([f"'{p}'" for p in renamed_paths])
                count_sql = f"SELECT SUM(cnt) FROM (SELECT COUNT(*) AS cnt FROM read_parquet([{files_list}]))"
                total_rows = con.execute(count_sql).fetchone()[0]

                result_stats[str(value)] = {
                    "paths": renamed_paths,
                    "total_rows": total_rows,
                    "num_parts": len(renamed_paths)
                }
                total_rows_all += total_rows

            return {
                "status": "completed",
                "total_files_processed": len(files),
                "unique_values": len(result_stats),
                "total_rows": total_rows_all,
                "details": result_stats,
                "output_dir": str(target_dir)
            }

    # ---------- Удобные обёртки для предопределённых путей ----------

    def split_data_by_columns_with_config(self, root_dir: Path, split_column: str) -> Dict[str, Any]:
        """
        Разбивает данные, используя self.raw_dir и self.test_dir как корневые директории.
        """
        source_dir = self.raw_dir / root_dir
        target_dir = self.test_dir / root_dir
        return self.split_data_by_columns(source_dir, target_dir, split_column)

    # ---------- Конвертация ----------

    def convert_parquet_to_csv(self, parquet_path: Path, csv_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Конвертирует Parquet файл в CSV.
        :param parquet_path: Путь к исходному Parquet файлу.
        :param csv_path: Путь для сохранения CSV. Если не указан, сохраняется рядом с исходным.
        :return: Словарь со статусом и статистикой.
        """
        parquet_path = Path(parquet_path)
        if not parquet_path.exists() or not parquet_path.is_file():
            return {"status": "error", "error": f"Parquet файл не найден: {parquet_path}"}

        if csv_path is None:
            csv_path = parquet_path.with_suffix('.csv')
        else:
            csv_path = Path(csv_path)
            csv_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with duckdb.connect() as con:
                con.execute(f"SET memory_limit='{self.memory_limit}'")
                con.execute("SET threads TO 4")

                export_sql = f"""
                    COPY (
                        SELECT * FROM read_parquet('{parquet_path.as_posix()}')
                    ) TO '{csv_path.as_posix()}' (
                        FORMAT CSV, 
                        HEADER, 
                        DELIMITER ','
                    )
                """
                con.execute(export_sql)

                row_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{parquet_path.as_posix()}')").fetchone()[0]

                return {
                    "status": "completed",
                    "source_file": str(parquet_path),
                    "target_file": str(csv_path),
                    "rows_exported": row_count
                }
        except Exception as e:
            logger.exception(f"Ошибка при конвертации в CSV: {e}")
            return {"status": "error", "error": str(e)}
