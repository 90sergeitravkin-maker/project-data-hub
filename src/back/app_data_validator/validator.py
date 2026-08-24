# src/back/app_data_validator/validator.py
"""
DataValidator — проверка CSV/Parquet/XLSX/XLS.
Агрегирует одинаковые ошибки, чтобы не выводить десятки тысяч дубликатов.
Автоматически ищет последнюю доступную версию справочника по дате в имени папки.
Поддерживает относительные пути к файлам.
"""
import csv
import re
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field, ValidationError, create_model
from src.core.logger import logger
from src.back.app_data_validator.config import BASE_DATA_DIR

try:
    import pyarrow.parquet as pq
except ImportError:
    pq = None
try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None
try:
    import xlrd
except ImportError:
    xlrd = None


class DataValidator:
    def __init__(self, config: dict, max_error_examples: int = 1000, max_duplicate_examples: int = 10):
        self.config = config
        self.max_error_examples = max_error_examples
        self.max_duplicate_examples = max_duplicate_examples
        self._ref_cache: Dict[Tuple[str, str], Set[str]] = {}

    @staticmethod
    def _resolve_file_path(file_path: str) -> str:
        """Преобразует относительный путь в абсолютный, используя BASE_DATA_DIR."""
        path = Path(file_path)
        if path.is_absolute() and path.exists():
            return str(path)

        # Если путь относительный, склеиваем его с BASE_DATA_DIR
        candidate = BASE_DATA_DIR / file_path
        if candidate.exists():
            logger.info(f"[Validator] Относительный путь разрешён: {file_path} -> {candidate}")
            return str(candidate)

        # Если не нашли, возвращаем исходный путь (чтобы ошибка ниже была понятной)
        return file_path

    def validate_file(self, file_path: str, source_name: str) -> Dict[str, Any]:
        if source_name not in self.config:
            return {"error": f"Источник {source_name} не найден в конфигурации"}
        column_rules = self.config[source_name]

        # === ВАЖНО: Разрешаем путь к файлу ПЕРЕД любыми операциями ===
        resolved_file_path = self._resolve_file_path(file_path)

        ext = Path(resolved_file_path).suffix.lower().lstrip('.')
        if ext not in ('csv', 'parquet', 'xlsx', 'xls'):
            return {"error": f"Неподдерживаемый формат: {ext}"}

        # Используем resolved_file_path для чтения заголовков
        actual_columns = self._get_columns(resolved_file_path, ext)
        if actual_columns is None:
            return {"error": f"Не удалось прочитать заголовки {resolved_file_path}"}

        required_cols = [c for c, r in column_rules.items() if r.get('required', False)]
        missing = [c for c in required_cols if c not in actual_columns]
        if missing:
            return {"error": f"Отсутствуют обязательные колонки: {missing}"}

        unique_cols = [c for c, r in column_rules.items() if r.get('unique', False)]
        unique_seen = {c: set() for c in unique_cols}
        duplicates_agg = {c: {} for c in unique_cols}

        ref_sets = self._preload_reference_sets(column_rules)
        Model = self._create_validation_model(column_rules)

        # АГРЕГАТОР ОШИБОК: (category, column_name, value) -> {count, first_row, error_text}
        error_agg: Dict[Tuple[str, Optional[str], Optional[str]], Dict[str, Any]] = {}

        processor = {
            'csv': self._process_csv,
            'parquet': self._process_parquet,
            'xlsx': self._process_xlsx,
            'xls': self._process_xls,
        }.get(ext)

        if not processor:
            return {"error": f"Неизвестный процессор для формата {ext}"}

        # Передаем resolved_file_path в процессор
        total_rows = processor(
            resolved_file_path, column_rules, Model,
            unique_seen, duplicates_agg, ref_sets, error_agg
        )

        # Добавляем дубликаты в агрегатор
        for col, dup_dict in duplicates_agg.items():
            for val, info in dup_dict.items():
                key = ("duplicate", col, val)
                error_agg[key] = {
                    "count": info["count"],
                    "first_row": info["rows"][0] if info["rows"] else None,
                    "error_text": f"Дубликат: {info['count']} вхождений",
                }

        # Формируем итоговый список ошибок
        errors: List[Dict[str, Any]] = []
        error_summary: Dict[str, int] = {}

        for (category, column_name, value), info in error_agg.items():
            count = info["count"]
            error_summary[category] = error_summary.get(category, 0) + count

            error_text = info["error_text"]
            if count > 1:
                error_text = f"{error_text} (встречается {count} раз)"

            errors.append({
                "category": category,
                "row_num": info.get("first_row"),
                "column_name": column_name,
                "value": value,
                "error_text": error_text,
                "count": count,
            })

        # Сортируем по частоте (самые частые — сверху)
        errors.sort(key=lambda x: x.get("count", 1), reverse=True)

        return {
            "file": resolved_file_path,  # Возвращаем абсолютный путь в ответе
            "source": source_name,
            "total_rows": total_rows,
            "status": "OK" if not errors else "FAIL",
            "error_summary": error_summary,
            "errors": errors[:self.max_error_examples],
        }

    @staticmethod
    def _add_error(error_agg: Dict, category: str, row_num: int, column_name: Optional[str],
                   value: Any, error_text: str) -> None:
        """Добавляет ошибку в агрегатор (схлопывает одинаковые)."""
        val_str = str(value).strip() if value is not None else None
        key = (category, column_name, val_str)
        if key in error_agg:
            error_agg[key]["count"] += 1
        else:
            error_agg[key] = {
                "count": 1,
                "first_row": row_num,
                "error_text": error_text,
            }

    @staticmethod
    def _convert_type(value: Any, type_name: str) -> Any:
        if value is None or (isinstance(value, str) and str(value).strip() == ''):
            return None
        s = str(value).strip()
        try:
            if type_name == "String":
                return s
            if type_name == "Int64":
                return int(float(s))
            if type_name in ("Float64", "Float32"):
                return float(s)
            if type_name == "Bool":
                return s.lower() in ('true', '1', 'yes', 'on', 'да')
            if type_name == "Date":
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"):
                    try:
                        return datetime.strptime(s, fmt).date()
                    except ValueError:
                        continue
                raise ValueError(f"Не удалось преобразовать '{s}' в Date")
            if type_name.startswith("Datetime"):
                return datetime.fromisoformat(s)
            raise ValueError(f"Неизвестный тип: {type_name}")
        except Exception as e:
            raise ValueError(str(e))

    @staticmethod
    def _map_type(type_name: str) -> type:
        mapping = {"String": str, "Int64": int, "Float64": float, "Float32": float,
                   "Bool": bool, "Date": date, "Datetime": datetime}
        return mapping.get(type_name.strip().split('(')[0], str)

    def _create_validation_model(self, column_rules: Dict[str, Dict]) -> type:
        fields = {}
        for col, rules in column_rules.items():
            py_type = self._map_type(rules.get('type', 'String'))
            required = rules.get('required', False)
            fields[col] = (Optional[py_type], Field(...)) if required else (Optional[py_type], Field(None))
        return create_model('DynamicModel', **fields)

    def _load_reference_set(self, file_path: str, column_name: str) -> Set[str]:
        key = (file_path, column_name)
        if key in self._ref_cache:
            return self._ref_cache[key]

        # Сначала делаем путь абсолютным (если он относительный)
        absolute_path = self._resolve_file_path(file_path)

        # Затем ищем актуальную версию по дате
        actual_file_path = self._resolve_latest_file_path(absolute_path)
        ext = Path(actual_file_path).suffix.lower()
        values: Set[str] = set()

        if not Path(actual_file_path).exists():
            logger.error(f"[Validator] Справочник не найден: {actual_file_path}")
            self._ref_cache[key] = values
            return values

        try:
            if ext == '.csv':
                with open(actual_file_path, 'r', encoding='utf-8') as f:
                    for row in csv.DictReader(f):
                        v = row.get(column_name)
                        if v is not None and str(v).strip():
                            values.add(str(v).strip())
            elif ext == '.parquet' and pq:
                table = pq.read_table(actual_file_path, columns=[column_name])
                for v in table[column_name].to_pylist():
                    if v is not None and str(v).strip():
                        values.add(str(v).strip())
            elif ext == '.xlsx' and load_workbook:
                wb = load_workbook(actual_file_path, read_only=True)
                ws = wb.active
                header = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
                try:
                    col_idx = header.index(column_name)
                except ValueError:
                    wb.close()
                    self._ref_cache[key] = values
                    return values
                for row in ws.iter_rows(min_row=2, values_only=True):
                    v = row[col_idx] if col_idx < len(row) else None
                    if v is not None and str(v).strip():
                        values.add(str(v).strip())
                wb.close()
            elif ext == '.xls' and xlrd:
                book = xlrd.open_workbook(actual_file_path, on_demand=True)
                sheet = book.sheet_by_index(0)
                header = sheet.row_values(0)
                try:
                    col_idx = header.index(column_name)
                except ValueError:
                    self._ref_cache[key] = values
                    return values
                for row_idx in range(1, sheet.nrows):
                    v = sheet.cell_value(row_idx, col_idx)
                    if v is not None and str(v).strip():
                        values.add(str(v).strip())
        except Exception as e:
            logger.error(f"[Validator] Ошибка загрузки справочника {actual_file_path}: {e}")

        self._ref_cache[key] = values
        return values

    @staticmethod
    def _resolve_latest_file_path(configured_path: str) -> str:
        """Если файл по заданному пути не найден, ищет актуальную версию в последней доступной папке с датой."""
        path = Path(configured_path)
        if path.exists():
            return str(path)

        filename = path.name
        parent_dir = path.parent
        grandparent_dir = parent_dir.parent

        if not grandparent_dir.exists() or not grandparent_dir.is_dir():
            return str(path)

        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        date_dirs = sorted(
            [d for d in grandparent_dir.iterdir() if d.is_dir() and date_pattern.match(d.name)],
            key=lambda x: x.name,
            reverse=True
        )

        if not date_dirs:
            logger.warning(f"[Validator] Папок с датами не найдено в {grandparent_dir}")
            return str(path)

        name_without_ext = filename.replace(path.suffix, '')
        name_without_date = re.sub(r'^\d{4}-\d{2}-\d{2}_', '', name_without_ext)
        pattern = f"*{name_without_date}{path.suffix}"

        for latest_date_dir in date_dirs:
            matching_files = list(latest_date_dir.glob(pattern))
            if matching_files:
                matching_files.sort(key=lambda x: x.name, reverse=True)
                resolved_path = str(matching_files[0])
                logger.info(f"[Validator] Справочник перенаправлен: {configured_path} -> {resolved_path}")
                return resolved_path

        logger.warning(f"[Validator] Файл по шаблону '{pattern}' не найден ни в одной папке-дате")
        return str(path)

    def _preload_reference_sets(self, column_rules: Dict) -> Dict[Tuple[str, str], Set[str]]:
        ref_sets = {}
        for col, rules in column_rules.items():
            for check in rules.get('checks', []):
                key = (check['reference_file'], check['reference_column'])
                if key not in ref_sets:
                    ref_sets[key] = self._load_reference_set(*key)
        return ref_sets

    def _get_columns(self, file_path: str, ext: str) -> Optional[List[str]]:
        try:
            if ext == 'csv':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return [h.strip() for h in next(csv.reader(f), [])]
            if ext == 'parquet' and pq:
                return list(pq.read_schema(file_path).names)
            if ext == 'xlsx' and load_workbook:
                wb = load_workbook(file_path, read_only=True)
                ws = wb.active
                header = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
                wb.close()
                return [str(cell).strip() if cell else '' for cell in header]
            if ext == 'xls' and xlrd:
                book = xlrd.open_workbook(file_path, on_demand=True)
                return [str(cell).strip() for cell in book.sheet_by_index(0).row_values(0)]
        except Exception as e:
            logger.error(f"[Validator] Ошибка чтения заголовков {file_path}: {e}")
            return None
        return None

    def _process_row(self, row: Dict, row_num: int, column_rules: Dict, Model,
                     unique_seen: Dict, duplicates_agg: Dict, ref_sets: Dict,
                     error_agg: Dict) -> None:
        converted = {}
        for col, rules in column_rules.items():
            raw = row.get(col)
            try:
                converted[col] = self._convert_type(raw, rules.get('type', 'String'))
            except ValueError as e:
                self._add_error(error_agg, "type_conversion", row_num, col, str(raw), str(e))
                converted[col] = None

        try:
            validated = Model(**converted)
        except ValidationError as e:
            for err in e.errors():
                self._add_error(
                    error_agg, "type_conversion", row_num,
                    '.'.join(str(l) for l in err['loc']), None, err['msg']
                )
            return

        for col, rules in column_rules.items():
            value = getattr(validated, col)
            value_str = str(value).strip() if value is not None else None

            for check in rules.get('checks', []):
                ref_key = (check['reference_file'], check['reference_column'])
                ref_set = ref_sets.get(ref_key)

                if value is None or value_str == '':
                    if check.get('is_null') is False:
                        self._add_error(
                            error_agg, "required_null", row_num, col, None,
                            f"Поле не может быть NULL (ref: {ref_key[1]})"
                        )
                    continue

                if ref_set is None:
                    self._add_error(
                        error_agg, "reference_not_loaded", row_num, col, value_str,
                        "Справочник не загружен"
                    )
                    continue

                if value_str not in ref_set:
                    self._add_error(
                        error_agg, "reference_failed", row_num, col, value_str,
                        "Значение не найдено в справочнике"
                    )

        for col in [c for c, r in column_rules.items() if r.get('unique', False)]:
            value = getattr(validated, col)
            if value is not None:
                value_str = str(value).strip()
                if value_str in unique_seen[col]:
                    dup_info = duplicates_agg[col].setdefault(value_str, {"count": 0, "rows": []})
                    dup_info["count"] += 1
                    if len(dup_info["rows"]) < self.max_duplicate_examples:
                        dup_info["rows"].append(row_num)
                else:
                    unique_seen[col].add(value_str)

    def _process_csv(self, file_path, column_rules, Model, unique_seen, duplicates_agg, ref_sets, error_agg):
        total = 0
        with open(file_path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                total += 1
                self._process_row(row, total, column_rules, Model, unique_seen, duplicates_agg, ref_sets, error_agg)
        return total

    def _process_parquet(self, file_path, column_rules, Model, unique_seen, duplicates_agg, ref_sets, error_agg):
        if pq is None:
            self._add_error(error_agg, "reference_not_loaded", None, None, None, "pyarrow не установлен")
            return 0
        table = pq.read_table(file_path)
        total = 0
        for batch in table.to_batches():
            for i in range(batch.num_rows):
                total += 1
                row = {col: batch.column(col)[i].as_py() for col in batch.schema.names if col in column_rules}
                self._process_row(row, total, column_rules, Model, unique_seen, duplicates_agg, ref_sets, error_agg)
        return total

    def _process_xlsx(self, file_path, column_rules, Model, unique_seen, duplicates_agg, ref_sets, error_agg):
        if load_workbook is None:
            return 0
        wb = load_workbook(file_path, read_only=True)
        ws = wb.active
        header = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
        col_index = {h: i for i, h in enumerate(header) if h is not None}
        total = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            total += 1
            row_dict = {col: row[col_index[col]] if col in col_index else None for col in column_rules}
            self._process_row(row_dict, total, column_rules, Model, unique_seen, duplicates_agg, ref_sets, error_agg)
        wb.close()
        return total

    def _process_xls(self, file_path, column_rules, Model, unique_seen, duplicates_agg, ref_sets, error_agg):
        if xlrd is None:
            return 0
        book = xlrd.open_workbook(file_path, on_demand=True)
        sheet = book.sheet_by_index(0)
        header = sheet.row_values(0)
        col_index = {h: i for i, h in enumerate(header) if h}
        total = 0
        for row_idx in range(1, sheet.nrows):
            total += 1
            row_dict = {col: sheet.cell_value(row_idx, col_index[col]) if col in col_index else None for col in
                        column_rules}
            self._process_row(row_dict, total, column_rules, Model, unique_seen, duplicates_agg, ref_sets, error_agg)
        return total
