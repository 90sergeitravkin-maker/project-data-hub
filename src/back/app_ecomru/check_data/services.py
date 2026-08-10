# src/back/app_ecomru/check_data/services.py
import asyncio
import os
import uuid
from pathlib import Path
from typing import Dict, Any, List, Union

from src.core.logger import logger
from src.core.kafka import kafka_client, InvalidMessageError
from src.back.app_ecomru.config import (
    DATA_FILE_RAW, DATA_FILE_TEMP,
    get_allowed_prefixes, get_split_columns,
)
from src.back.app_ecomru.check_data.config import PROCESS_FOLDER_RESULT_TOPIC
from src.back.app_ecomru.check_data.file_manager import DuckDBFileManager


# ИСПРАВЛЕНО: добавлено подчеркивание, чтобы совпадало с вызовами ниже
def _validate_folder(path: Path, *,
                     require_read=False,
                     require_write=False,
                     base_path: Path = DATA_FILE_RAW,
                     check_inside_base=True,
                     allow_create_parent=False,
                     must_not_equal=None) -> Dict[str, Any]:
    """Валидация путей: существование, права, безопасность (выход за пределы базы)."""
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


def process_data_folder(
        folder_path: str,
        split_columns: Union[str, List[str], None] = None,
) -> Dict[str, Any]:
    """
    Обработка папки с данными.

    Args:
        folder_path: Относительный путь внутри DATA_FILE_RAW
            (например, "API-COMTRADE-WORLD_TRADE-1/2026-07-21/202302")
        split_columns: Столбец (str) или список столбцов (List[str]) для разбиения.
            Если None — определяется из _fields_config.json по entity (hot-reload).

    Returns:
        Словарь с результатом преобразования
    """
    if not folder_path or not folder_path.strip():
        return {"status": "error", "error": "Путь к папке не может быть пустым."}

    normalized = Path(folder_path).as_posix()
    parts = Path(normalized).parts

    if not parts:
        return {"status": "error", "error": "Путь не содержит компонентов."}

    # Hot-reload: читаем разрешённые префиксы с диска каждый раз
    allowed = get_allowed_prefixes()
    if parts[0] not in allowed:
        return {"status": "error", "error": f"Недопустимый префикс. Разрешены: {allowed}"}

    entity = parts[0]

    # Нормализация split_columns в список
    if split_columns is None:
        split_columns = get_split_columns(entity)
    elif isinstance(split_columns, str):
        split_columns = [split_columns]

    if not split_columns:
        return {"status": "error",
                "error": f"Не определены столбцы разбиения для entity '{entity}'"}

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
        # Передаём СПИСОК столбцов
        result = manager.split_data_by_columns(raw_folder, target_folder, split_columns)
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

    logger.info(f"Разбиение завершено: создано {result['unique_values']} групп "
                f"по столбцам {split_columns}")

    checksum_result = manager.get_comtrade_checksum_control(target_folder)
    logger.info(f"Результат контрольной суммы: {checksum_result}")

    return {
        "status": "completed",
        "split_result": result,
        "checksum_result": checksum_result,
    }


async def handle_process_folder_task(task: Dict[str, Any]) -> None:
    """Обработчик задач из топика process-folder."""
    folder_path = task.get("folder_path")
    # Поддержка и split_column (строка), и split_columns (список)
    split_columns = task.get("split_columns") or task.get("split_column")
    task_id = task.get("task_id") or str(uuid.uuid4())

    if not folder_path:
        raise InvalidMessageError("Отсутствует folder_path в задаче")

    logger.info(f"[PROCESS_FOLDER] Получена задача: folder={folder_path}, "
                f"columns={split_columns}, task_id={task_id}")

    try:
        # split_columns может быть None → определится из конфига (hot-reload)
        result = await asyncio.to_thread(process_data_folder, folder_path, split_columns)

        result_message = {
            "task_id": task_id,
            "status": "completed",
            "result": result,
            "folder_path": folder_path,
            "split_columns": split_columns,
        }
        await kafka_client.send_message(PROCESS_FOLDER_RESULT_TOPIC, value=result_message, key=task_id)
        logger.info(
            f"[PROCESS_FOLDER] ✅ Задача {task_id} выполнена, результат отправлен в {PROCESS_FOLDER_RESULT_TOPIC}")
    except Exception as e:
        logger.error(f"[PROCESS_FOLDER] ❌ Ошибка выполнения задачи {task_id}: {e}", exc_info=True)
        error_message = {
            "task_id": task_id,
            "status": "error",
            "error": str(e),
            "folder_path": folder_path,
            "split_columns": split_columns,
        }
        await kafka_client.send_message(PROCESS_FOLDER_RESULT_TOPIC, value=error_message, key=task_id)
        raise
