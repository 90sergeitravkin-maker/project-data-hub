# src/back/app_ecomru/check_data/services.py
import os
from pathlib import Path
from typing import Dict, Any, Optional

from core.logger import logger
from src.back.app_ecomru.config import DATA_FILE_RAW, DATA_FILE_TEMP, ALLOWED_PREFIXES
from src.back.app_ecomru.check_data.file_manager import DuckDBFileManager


def _validate_folder(path: Path, *, require_read=False, require_write=False,
                     base_path: Path = DATA_FILE_RAW, check_inside_base=True,
                     allow_create_parent=False, must_not_equal=None) -> Dict[str, Any]:
    """(без изменений — ваш существующий код)"""
    if not path.exists():
        if allow_create_parent:
            try:
                path.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                return {"status": "error", "error": f"Нет прав на создание папки: {path}"}
        else:
            return {"status": "error", "error": f"Папка не найдена: {path}"}
    if not path.is_dir():
        return {"status": "error", "error": f"Не является папкой: {path}"}
    if require_read and not os.access(path, os.R_OK):
        return {"status": "error", "error": f"Нет прав на чтение: {path}"}
    if require_write and not os.access(path, os.W_OK):
        return {"status": "error", "error": f"Нет прав на запись: {path}"}
    if check_inside_base:
        try:
            path.relative_to(base_path)
        except ValueError:
            return {"status": "error", "error": f"Путь {path} вне {base_path}"}
    if must_not_equal is not None and path == must_not_equal:
        return {"status": "error", "error": "Совпадение исходной и целевой папки"}
    return {"status": "ok", "path": path}


def process_data_folder(folder_path: str, split_column: str = "dataset_checksum") -> Dict[str, Any]:
    """
    Обработка папки с данными.

    Args:
        folder_path: Относительный путь внутри DATA_FILE_RAW
                     (например, "API-COMTRADE-WORLD_TRADE-1/2026-07-21/202302")
        split_column: Столбец для разбиения файлов

    Returns:
        Словарь с результатом преобразования
    """
    if not folder_path or not folder_path.strip():
        return {"status": "error", "error": "Путь к папке не может быть пустым."}

    normalized = Path(folder_path).as_posix()
    parts = Path(normalized).parts
    if not parts:
        return {"status": "error", "error": "Путь не содержит компонентов."}
    if parts[0] not in ALLOWED_PREFIXES:
        return {"status": "error", "error": f"Недопустимый префикс. Разрешены: {ALLOWED_PREFIXES}"}

    raw_folder = DATA_FILE_RAW / normalized

    src_check = _validate_folder(raw_folder, require_read=True, base_path=DATA_FILE_RAW)
    if "error" in src_check:
        return {"status": "error", "error": src_check["error"]}

    try:
        rel_path = raw_folder.relative_to(DATA_FILE_RAW)
    except ValueError:
        return {"status": "error", "error": f"Путь {raw_folder} вне DATA_FILE_RAW"}

    target_folder = DATA_FILE_TEMP / rel_path

    target_check = _validate_folder(
        target_folder, require_write=True, base_path=DATA_FILE_TEMP,
        check_inside_base=False, allow_create_parent=True, must_not_equal=raw_folder
    )
    if "error" in target_check:
        return {"status": "error", "error": target_check["error"]}

    manager = DuckDBFileManager()
    manager.remove_suffix_from_files(str(raw_folder), 'parquet')

    parquet_files = list(raw_folder.rglob("*.parquet"))
    if not parquet_files:
        return {"status": "empty", "message": "Нет parquet-файлов"}

    try:
        result = manager.split_data_by_columns(raw_folder, target_folder, split_column)
    except Exception as e:
        logger.exception("Ошибка при разбиении")
        return {"status": "error", "error": f"Ошибка при разбиении: {str(e)}"}

    if result.get('status') != 'completed':
        return result

    details = result.get('details', {})
    for key, info in details.items():
        abs_paths = info.get('paths', [])
        rel_paths = []
        for p in abs_paths:
            try:
                rel = Path(p).relative_to(DATA_FILE_TEMP)
                rel_paths.append(rel.as_posix())
            except ValueError:
                rel_paths.append(p)
        info['paths'] = rel_paths

    logger.info(f"Разбиение завершено: создано {result['unique_values']} групп")

    checksum_result = manager.get_comtrade_checksum_control(target_folder)
    logger.info(f"Результат контрольной суммы: {checksum_result}")

    return {
        "status": "completed",
        "split_result": result,
        "checksum_result": checksum_result,
    }