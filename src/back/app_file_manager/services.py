# src/back/app_file_manager/download.py
import csv
import io
import json
import re
import asyncio
import hashlib
import duckdb

from datetime import datetime
from pathlib import Path
from functools import lru_cache
from typing import List, Tuple, Dict, Any, Optional, Set

from src.core.logger import logger
from src.core.data_checker import DataChecker
from src.core.type_unifier import SchemaComparator
from src.back.app_file_manager.config import DATA_ROOT_DIR
from src.database.manager import DBManager


class AppDataChecker:
    _comparator = SchemaComparator()
    EXCLUDED_FOLDERS: Set[str] = {
        '.git', '__pycache__', '.venv', 'venv', 'node_modules',
        '.idea', '.vscode', 'logs', 'tmp', 'temp', '.cache',
        '.pytest_cache', '.mypy_cache', 'dist', 'build', 'egg-info'
    }

    # === Утилиты ===
    @staticmethod
    def _paginate_list(items: list, page: int, page_size: int) -> Dict[str, Any]:
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "items": items[start:end],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": end < total,
            "has_prev": page > 1,
            "total_pages": max(1, (total + page_size - 1) // page_size)
        }

    @staticmethod
    @lru_cache(maxsize=256)
    def _map_duckdb_type_cached(duckdb_type: str) -> str:
        if not duckdb_type:
            return "VARCHAR"
        return AppDataChecker._comparator._normalize_type(
            duckdb_type,
            SchemaComparator.TYPE_MAPPING.get('duckdb', {})
        )

    @staticmethod
    def _detect_file_type(path: Path) -> str:
        try:
            with open(path, 'rb') as f:
                header = f.read(4)
            if header == b'PAR1':
                return 'parquet'
        except (OSError, IOError):
            pass
        name = path.name.lower()
        for suffix in ['.sended', '.processed', '.tmp', '.bak']:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break
        ext = Path(name).suffix.lower()
        type_map = {
            '.parquet': 'parquet',
            '.csv': 'csv', '.txt': 'csv', '.tsv': 'csv',
            '.json': 'json', '.jsonl': 'json', '.ndjson': 'json'
        }
        return type_map.get(ext, 'csv')

    @staticmethod
    def _parse_null_flag(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().upper() in ('YES', 'TRUE', '1', 'T')
        return True

    # === Чтение схем ===
    @staticmethod
    def _read_schema_generic(query: str) -> Dict[str, Dict[str, Any]]:
        con = duckdb.connect()
        try:
            result = con.execute(query).fetchall()
            schema = {}
            for row in result:
                col_name = row[0]
                col_type_raw = row[1]
                col_null_raw = row[2] if len(row) > 2 else 'YES'
                schema[col_name] = {
                    "type": AppDataChecker._map_duckdb_type_cached(col_type_raw),
                    "null": AppDataChecker._parse_null_flag(col_null_raw)
                }
            return schema
        finally:
            con.close()

    @staticmethod
    def _read_parquet_schema_duckdb(path: Path) -> Dict[str, Dict[str, Any]]:
        safe_path = path.as_posix().replace("'", "''")
        query = f"DESCRIBE (SELECT * FROM read_parquet('{safe_path}'))"
        return AppDataChecker._read_schema_generic(query)

    @staticmethod
    def _read_json_schema_duckdb(path: Path) -> Dict[str, Dict[str, Any]]:
        safe_path = path.as_posix().replace("'", "''")
        query = f"DESCRIBE (SELECT * FROM read_json_auto('{safe_path}'))"
        return AppDataChecker._read_schema_generic(query)

    @staticmethod
    def _read_csv_schema_duckdb(path: Path) -> Dict[str, Dict[str, Any]]:
        safe_path = path.as_posix().replace("'", "''")
        query = f"DESCRIBE (SELECT * FROM read_csv_auto('{safe_path}'))"
        return AppDataChecker._read_schema_generic(query)

    @staticmethod
    def _read_text_schema_as_varchar(path: Path) -> Dict[str, Dict[str, Any]]:
        encodings = ['utf-8-sig', 'cp1251', 'windows-1252', 'latin-1']
        sample_text = None
        used_enc = 'utf-8-sig'
        for enc in encodings:
            try:
                with open(path, 'r', encoding=enc, newline='') as f:
                    sample_text = f.read(4096)
                used_enc = enc
                break
            except UnicodeDecodeError:
                continue
            except OSError as e:
                logger.error(f"Ошибка доступа к файлу {path.name}: {e}")
                raise
        if not sample_text:
            raise ValueError(f"Не удалось прочитать {path.name} в поддерживаемых кодировках")
        if used_enc != 'utf-8-sig':
            logger.warning(f"Файл {path.name} прочитан с резервной кодировкой: {used_enc}")
        sample_text = sample_text.replace('\r\n', '\n').replace('\r', '\n')
        try:
            dialect = csv.Sniffer().sniff(sample_text, delimiters=',;\t|')
        except csv.Error:
            dialect = csv.excel
        try:
            reader = csv.reader(io.StringIO(sample_text), dialect)
            headers = next(reader, [])
            clean_headers = [h.strip().strip('"\'') for h in headers if h.strip()]
            if not clean_headers:
                raise ValueError("Файл не содержит валидных заголовков или пуст")
            logger.debug(f"Извлечены заголовки ({len(clean_headers)} полей) из {path.name}, кодировка: {used_enc}")
            return {col: {"type": "VARCHAR", "null": True} for col in clean_headers}
        except StopIteration:
            raise ValueError("Файл пуст")
        except csv.Error as e:
            raise ValueError(f"Ошибка формата CSV/TXT: {e}")

    # === Сканирование директорий ===
    # src/back/app_file_manager/download.py

    @staticmethod
    async def get_available_folders(
            root_dir: Path,
            folder_path: Optional[str] = None,
            pattern: Optional[str] = None,
            page: int = 1,
            page_size: int = 50
    ) -> Tuple[bool, Dict[str, Any]]:
        try:
            if not root_dir or not root_dir.exists() or not root_dir.is_dir():
                logger.error(f"[SCAN] Неверная корневая директория: {root_dir}")
                return False, {'error': 'Неверная корневая директория'}

            root_dir_resolved = root_dir.resolve()

            if folder_path:
                normalized = folder_path.strip().lstrip('/').lstrip('\\')
                path_parts = normalized.replace('\\', '/').split('/')
                if '..' in path_parts or not normalized:
                    logger.warning(f"[SCAN] Попытка обхода директорий: folder_path={folder_path!r}")
                    return False, {'error': 'Доступ запрещён: невалидный путь'}
                target_dir = (root_dir_resolved / normalized).resolve()
            else:
                target_dir = root_dir_resolved

            # Проверка безопасности: путь должен быть внутри корня
            if not str(target_dir).startswith(str(root_dir_resolved)):
                logger.warning(f"[SCAN] Доступ запрещён: target_dir={target_dir}")
                return False, {'error': 'Доступ запрещён: путь выходит за пределы корневой директории'}

            # ✅ ИСПРАВЛЕНО: Если директория не найдена — возвращаем пустой результат, а не ошибку
            if not target_dir.exists() or not target_dir.is_dir():
                logger.debug(f"[SCAN] Директория не найдена: {folder_path} — возвращаем пустой результат")
                return True, {
                    'folders': [],
                    'files': [],
                    'total': 0,
                    'page': page,
                    'page_size': page_size,
                    'has_next': False,
                    'has_prev': False,
                    'current_path': folder_path or '',
                }

            all_items: List[Path] = []
            try:
                all_items = [p for p in target_dir.iterdir() if not p.name.startswith('.')]
            except PermissionError:
                return False, {'error': f'Нет прав на чтение: {folder_path}'}

            # Применяем regex-фильтр, если указан
            if pattern:
                try:
                    regex = re.compile(pattern, re.IGNORECASE)
                    all_items = [p for p in all_items if regex.search(p.name)]
                except re.error as e:
                    return False, {'error': f'Некорректный паттерн: {pattern}'}

            folders: List[str] = sorted([p.name for p in all_items if p.is_dir()])
            files: List[str] = sorted([p.name for p in all_items if p.is_file()])
            total: int = len(folders) + len(files)

            start_idx: int = (page - 1) * page_size
            end_idx: int = start_idx + page_size

            all_names: List[tuple] = [(name, 'folder') for name in folders] + [(name, 'file') for name in files]
            paginated: List[tuple] = all_names[start_idx:end_idx]

            paginated_folders: List[str] = [n for n, t in paginated if t == 'folder']
            paginated_files: List[str] = [n for n, t in paginated if t == 'file']

            return True, {
                'folders': paginated_folders,
                'files': paginated_files,
                'total': total,
                'page': page,
                'page_size': page_size,
                'has_next': end_idx < total,
                'has_prev': page > 1,
                'current_path': folder_path or '',
            }
        except Exception as e:
            error_location = "src/back/app_file_manager, download.py, строка ~120"
            logger.error(f"[SCAN] Критическая ошибка: {type(e).__name__}: {e} | {error_location}", exc_info=True)
            return False, {'error': f'Внутренняя ошибка сервиса: {type(e).__name__}', 'location': error_location}

    # src/back/app_file_manager/download.py

    # Добавьте в класс AppDataChecker

    @staticmethod
    async def search_in_directory(
            root_dir: Path,
            folder_path: Optional[str],
            search_query: str,
            page: int = 1,
            page_size: int = 50
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Рекурсивный поиск файлов и папок по имени (substring, case-insensitive).
        Ищет в указанной директории и всех поддиректориях.
        """
        try:
            if not root_dir or not root_dir.exists() or not root_dir.is_dir():
                logger.error(f"[SEARCH] Неверная корневая директория: {root_dir}")
                return False, {'error': 'Неверная корневая директория'}

            root_dir_resolved = root_dir.resolve()

            # Определяем директорию для поиска
            if folder_path:
                normalized = folder_path.strip().lstrip('/').lstrip('\\')
                path_parts = normalized.replace('\\', '/').split('/')
                if '..' in path_parts or not normalized:
                    return False, {'error': 'Доступ запрещён: невалидный путь'}
                target_dir = (root_dir_resolved / normalized).resolve()
            else:
                target_dir = root_dir_resolved

            # Проверка безопасности
            if not str(target_dir).startswith(str(root_dir_resolved)):
                return False, {'error': 'Доступ запрещён: путь выходит за пределы корня'}

            # Если директории нет, ищем по всему корню
            if not target_dir.exists() or not target_dir.is_dir():
                target_dir = root_dir_resolved

            # Рекурсивный поиск в отдельном потоке
            query_lower = search_query.lower()

            def _search_blocking() -> List[Dict[str, Any]]:
                found_items = []
                try:
                    for item in target_dir.rglob('*'):
                        # Пропускаем скрытые файлы/папки
                        if any(part.startswith('.') for part in item.parts):
                            continue

                        # Проверяем совпадение по имени
                        if query_lower in item.name.lower():
                            try:
                                rel_path = item.relative_to(root_dir_resolved)
                                found_items.append({
                                    'name': item.name,
                                    'path': str(rel_path).replace('\\', '/'),
                                    'is_dir': item.is_dir(),
                                })
                            except (ValueError, OSError):
                                continue
                except PermissionError:
                    logger.warning(f"[SEARCH] Нет прав на чтение: {target_dir}")
                return found_items

            # Выполняем поиск в отдельном потоке
            loop = asyncio.get_event_loop()
            found_items = await loop.run_in_executor(None, _search_blocking)

            # Сортируем: папки сначала, потом файлы
            found_items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))

            # Пагинация
            total = len(found_items)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated = found_items[start_idx:end_idx]

            # Разделяем на папки и файлы
            folders_data = [i for i in paginated if i['is_dir']]
            files_data = [i for i in paginated if not i['is_dir']]

            return True, {
                'folders': folders_data,
                'files': files_data,
                'total': total,
                'page': page,
                'page_size': page_size,
                'has_next': end_idx < total,
                'has_prev': page > 1,
                'current_path': folder_path or '',
                'search_query': search_query,
                'search_base_path': str(target_dir.relative_to(root_dir_resolved)).replace('\\', '/'),
            }
        except Exception as e:
            error_location = "src/back/app_file_manager/download.py, search_in_directory"
            logger.error(f"[SEARCH] Критическая ошибка: {type(e).__name__}: {e} | {error_location}", exc_info=True)
            return False, {'error': f'Внутренняя ошибка: {type(e).__name__}'}

    # === Извлечение схемы ===
    @staticmethod
    def _extract_schema_blocking(file_path: str, base: Path, detected_type: str) -> Dict[str, Dict[str, Any]]:
        full_path = (base / file_path).resolve()
        try:
            full_path.relative_to(base)
        except ValueError:
            raise PermissionError(f"Путь {file_path} выходит за пределы {base}")
        if not full_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        if not full_path.is_file():
            raise ValueError(f"Путь не является файлом: {file_path}")

        match detected_type:
            case "parquet":
                return AppDataChecker._read_parquet_schema_duckdb(full_path)
            case "csv":
                return AppDataChecker._read_csv_schema_duckdb(full_path)
            case "json":
                return AppDataChecker._read_json_schema_duckdb(full_path)
            case _:
                raise ValueError(f"Неподдерживаемый тип файла: {full_path.suffix}")

    @staticmethod
    def extract_file_schema_sync(file_path: str) -> Tuple[bool, Dict[str, Any]]:
        try:
            base = Path(DATA_ROOT_DIR).resolve()
            full_path = (base / file_path).resolve()
            detected_type = AppDataChecker._detect_file_type(full_path)
            schema = AppDataChecker._extract_schema_blocking(file_path, base, detected_type)
            return True, {"schema": schema, "file_type": detected_type, "field_count": len(schema)}
        except (PermissionError, FileNotFoundError, ValueError) as e:
            return False, {"error": str(e)}
        except duckdb.Error as e:
            return False, {"error": f"DuckDB: {str(e)}"}
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}", exc_info=True)
            return False, {"error": str(e)}

    @staticmethod
    async def extract_file_schema(file_path: str) -> Tuple[bool, Dict[str, Any]]:
        success, result = await asyncio.to_thread(AppDataChecker.extract_file_schema_sync, file_path)
        if success and result.get("schema"):
            try:
                asyncio.get_running_loop().create_task(
                    AppDataChecker._log_extraction_to_db(file_path, result["schema"],
                                                         result.get("file_type", "unknown"))
                )
            except RuntimeError:
                pass
        return success, result

    @staticmethod
    async def _log_extraction_to_db(file_path: str, schema: dict, file_type: str) -> bool:
        try:
            db = DBManager()
            await db.execute(
                "app_file_manager",
                "INSERT INTO schema_extraction_log (file_path, file_type, schema_json, extracted_at) VALUES ($1, $2, $3, NOW())",
                file_path, file_type, json.dumps(schema, ensure_ascii=False)
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка записи в БД: {e}", exc_info=True)
            return False

    @staticmethod
    async def check_comtrade_data(base_url: Path, folders: Optional[List[str]] = None) -> Tuple[bool, Dict[str, Any]]:
        return await DataChecker.check_data_list(base_url=base_url, folders=folders)

    @staticmethod
    async def upload_file_to_storage(file_path: str, file_content: bytes, overwrite: bool = False) -> Tuple[
        bool, Dict[str, Any]]:
        try:
            base_dir = Path(DATA_ROOT_DIR).resolve()
            target_path = (base_dir / file_path).resolve()
            if not str(target_path).startswith(str(base_dir)):
                raise PermissionError("Путь выходит за пределы разрешённой директории")
            if target_path.exists() and target_path.is_dir():
                return False, {"error": f"Указанный путь является директорией."}
            if target_path.exists() and not overwrite:
                return False, {"error": f"Файл уже существует."}

            target_path.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(target_path.write_bytes, file_content)
            return True, {"file_size": len(file_content), "stored_in": "local",
                          "checksum": hashlib.sha256(file_content).hexdigest()}
        except Exception as e:
            logger.error(f"Ошибка сохранения файла: {e}", exc_info=True)
            return False, {"error": str(e)}

    @staticmethod
    def _find_max_date_subfolder(folder_path: Path) -> Optional[str]:
        if not folder_path.is_dir(): return None
        max_dt, max_name = None, None
        date_re = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        for item in folder_path.iterdir():
            if item.is_dir() and date_re.match(item.name):
                try:
                    dt = datetime.strptime(item.name, "%Y-%m-%d")
                except ValueError:
                    continue
                if max_dt is None or dt > max_dt:
                    max_dt, max_name = dt, item.name
        return max_name

    @staticmethod
    async def get_max_dates_for_folders(folders: List[str], root_dir: Path) -> Dict[str, Optional[str]]:
        tasks = [asyncio.to_thread(AppDataChecker._find_max_date_subfolder, root_dir / f) for f in folders]
        return dict(zip(folders, await asyncio.gather(*tasks)))

    # === ПРЕВЬЮ ФАЙЛА С ФИЛЬТРАЦИЕЙ ===
    @staticmethod
    async def preview_file_content(
            file_path: str,
            base_dir: Path,
            page: int = 1,
            page_size: int = 50,
            max_rows: int = 1000,
            column_filters: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        try:
            normalized_path = file_path.strip().lstrip('/').lstrip('\\')
            full_path = (base_dir / normalized_path).resolve()
            try:
                full_path.relative_to(base_dir.resolve())
            except ValueError:
                return False, {'error': 'Доступ запрещён: путь вне разрешённой директории'}

            if not full_path.exists() or not full_path.is_file():
                return False, {'error': f'Файл не найден: {file_path}'}

            file_type = AppDataChecker._detect_file_type(full_path)
            if file_type not in {'parquet', 'csv', 'json', 'jsonl'}:
                return False, {'error': f'Неподдерживаемый формат: {file_type}'}

            con = duckdb.connect(':memory:')
            try:
                safe_path = full_path.as_posix().replace("'", "''")

                if file_type == 'parquet':
                    base_query = f"SELECT * FROM read_parquet('{safe_path}')"
                elif file_type == 'csv':
                    base_query = f"SELECT * FROM read_csv_auto('{safe_path}')"
                else:
                    base_query = f"SELECT * FROM read_json_auto('{safe_path}')"

                describe_query = f"DESCRIBE ({base_query})"
                available_cols = [row[0] for row in con.execute(describe_query).fetchall()]
                available_cols_set = set(available_cols)

                where_conditions = []
                params = []
                if column_filters:
                    for col, val in column_filters.items():
                        if val and col in available_cols_set:
                            if not re.match(r'^[a-zA-Zа-яА-ЯёЁ0-9_\-\.\ \(\)\[\]]+$', col, re.UNICODE):
                                logger.warning(f"[PREVIEW] Пропущен фильтр для подозрительной колонки: {col!r}")
                                continue
                            safe_col = col.replace('"', '""')
                            where_conditions.append(f'"{safe_col}"::VARCHAR ILIKE ?')
                            params.append(f'%{val}%')
                        elif val and col not in available_cols_set:
                            logger.debug(f"[PREVIEW] Фильтр пропущен: колонка '{col}' не найдена в файле")

                where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

                count_query = f"SELECT COUNT(*) FROM ({base_query}) {where_clause}"
                total_rows = con.execute(count_query, params).fetchone()[0]

                if total_rows > max_rows:
                    total_rows = max_rows

                offset = (page - 1) * page_size
                if offset >= total_rows:
                    return True, {
                        'columns': [], 'total_rows': total_rows, 'rows': [],
                        'file_type': file_type, 'page': page, 'page_size': page_size,
                        'has_next': False, 'message': f'Страница {page} вне диапазона'
                    }

                paginated_query = f"{base_query} {where_clause} LIMIT ? OFFSET ?"
                params.extend([page_size, offset])

                cursor = con.execute(paginated_query, params)
                result_columns = [desc[0] for desc in cursor.description]
                raw_rows = cursor.fetchall()

                rows = []
                for row in raw_rows:
                    row_dict = {}
                    for col, val in zip(result_columns, row):
                        if val is None:
                            row_dict[col] = None
                        elif hasattr(val, 'isoformat'):
                            row_dict[col] = val.isoformat()
                        elif isinstance(val, (list, dict)):
                            row_dict[col] = val
                        else:
                            row_dict[col] = val
                    rows.append({'data': row_dict})

                return True, {
                    'columns': result_columns, 'total_rows': total_rows, 'rows': rows,
                    'file_type': file_type, 'page': page, 'page_size': page_size,
                    'has_next': offset + page_size < total_rows,
                    'message': f'Показано строк: {len(rows)} из {total_rows}'
                }
            finally:
                con.close()
        except duckdb.Error as e:
            logger.error(f"[PREVIEW] DuckDB ошибка: {e}")
            return False, {'error': f'Ошибка чтения файла: {str(e)}'}
        except Exception as e:
            error_location = "src/back/app_file_manager, download.py, строка ~350"
            logger.error(f"[PREVIEW] Критическая ошибка: {type(e).__name__}: {e} | {error_location}", exc_info=True)
            return False, {'error': f'Внутренняя ошибка: {type(e).__name__}'}
