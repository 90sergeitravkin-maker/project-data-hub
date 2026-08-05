# src/back/app_ecomru/services.py
import asyncio
from pathlib import Path
from typing import Dict, Any, List

from src.core.logger import logger
from src.core.kafka import kafka_client, InvalidMessageError
from src.back.app_ecomru.config import (
    KAFKA_TRANSFER_TOPIC,
)
from src.back.app_ecomru.download.download import download_and_move_atomically
from src.back.app_datasets.services import DataSetsVerifiedServices
from src.back.app_ecomru.check_data.services import process_data_folder
from src.back.app_link.services import Link


async def _save_links_to_app_link(urls: list[str]) -> None:
    """
    Сохраняет ссылки в app_link с дедупликацией и отправкой в Kafka.
    Логирует количество новых и дублирующихся ссылок.
    Ошибки не пробрасывает — не должны ломать основной pipeline скачивания.
    """
    if not urls:
        return
    try:
        result = await Link.process_links(urls)
        new_count = sum(1 for r in result.results if r.status == "new")
        dup_count = sum(1 for r in result.results if r.status == "duplicate")
        logger.info(
            f"[DOWNLOAD] app_link: новых={new_count}, дубликатов={dup_count}"
        )
    except Exception as e:
        logger.error(
            f"[DOWNLOAD] Ошибка сохранения в app_link: {e}",
            exc_info=True,
        )


# ============================================================
# ЭТАП 1: СКАЧИВАНИЕ
# ============================================================
async def handle_download_task(task: Dict[str, Any]) -> None:
    """
    Обработчик задач из топика 'ecomru-download'.
    Поддерживает два формата:
      1. Новый: {"task_id": str, "urls": List[str], "dest_path": str, ...}
      2. Старый: {"url": str|List[str], "relative_path": str, ...}
    """
    # ---- Адаптация формата ----
    if "url" in task and "relative_path" in task:
        urls = task["url"] if isinstance(task["url"], list) else [task["url"]]
        rel_path = Path(task["relative_path"])
        parts = rel_path.parts
        if len(parts) >= 3:
            entity, updated_at, period = parts[0], parts[1], parts[2]
        else:
            entity = task.get("entity", parts[0] if parts else "")
            updated_at = task.get("updated_at", parts[1] if len(parts) > 1 else "")
            period = task.get("period", parts[2] if len(parts) > 2 else "")
        data = {
            "entity": entity,
            "updated_at": updated_at,
            "period": period,
            "links": urls,
        }
    else:
        # Новый формат: есть urls и dest_path
        urls = task.get("urls", [])
        dest_path = task.get("dest_path", "").strip("/")
        if not urls:
            raise InvalidMessageError(f"[DOWNLOAD] Нет URL для скачивания: {task}")

        parts = Path(dest_path).parts
        if len(parts) >= 3:
            entity, updated_at, period = parts[0], parts[1], parts[2]
        else:
            entity = task.get("entity", parts[0] if parts else "")
            updated_at = task.get("updated_at", parts[1] if len(parts) > 1 else "")
            period = task.get("period", parts[2] if len(parts) > 2 else "")
        data = {
            "entity": entity,
            "updated_at": updated_at,
            "period": period,
            "links": urls,
        }

    logger.info(f"[DOWNLOAD] Получена задача: {data}")

    try:
        moved_files: List[Path] = await asyncio.to_thread(
            download_and_move_atomically, data
        )
        logger.info(
            f"[DOWNLOAD] Задача выполнена успешно, перемещено файлов: {len(moved_files)}"
        )

        # Сохраняем метаданные каждого файла в app_datasets
        for file_path in moved_files:
            try:
                await DataSetsVerifiedServices.save_file_metadata(
                    file_path,
                    entity=entity,
                    period=period,
                    updated_at=updated_at,
                )
                logger.debug(f"[DOWNLOAD] Метаданные сохранены для {file_path.name}")
            except Exception as e:
                logger.error(
                    f"[DOWNLOAD] Ошибка сохранения метаданных для {file_path}: {e}",
                    exc_info=True,
                )
        await _save_links_to_app_link(data.get("links", []))

    except Exception as e:
        logger.error(f"[DOWNLOAD] Ошибка выполнения задачи: {e}", exc_info=True)
        raise  # ← пробрасываем, чтобы Kafka-клиент сделал retry


# ============================================================
# ЭТАП 2: ПРЕОБРАЗОВАНИЕ (разбиение по столбцу)
# ============================================================
async def handle_verification_task(task: Dict[str, Any]) -> None:
    """
    Этап 2: Преобразование (разбиение файлов по столбцу).
    """
    folder_path = task.get("folder_path")
    split_column = task.get("split_column", "dataset_checksum")
    entity = task.get("entity", "")
    updated_at = task.get("updated_at", "")
    period = task.get("period", "")

    if not folder_path or not isinstance(folder_path, str):
        raise InvalidMessageError(
            f"[VERIFICATION] Невалидное сообщение: отсутствует или некорректен "
            f"folder_path. task={task}"
        )

    logger.info(
        f"[VERIFICATION] Получена задача: folder={folder_path}, column={split_column}"
    )

    # ---- Разбиение ----
    result = await asyncio.to_thread(process_data_folder, folder_path, split_column)
    status = result.get("status")

    if status == "error":
        raise RuntimeError(f"[VERIFICATION] Ошибка: {result.get('error')}")
    if status == "empty":
        logger.warning(f"[VERIFICATION] Нет файлов: {result.get('message')}")
        return  # не ошибка — коммитим offset

    split_result = result.get("split_result", {})
    checksum_result = result.get("checksum_result", {})
    logger.info(
        f"[VERIFICATION] ✅ Завершено: "
        f"групп={split_result.get('unique_values', 0)}, "
        f"строк={split_result.get('total_rows', 0)}, "
        f"checksums={len(checksum_result)}"
    )

    # ---- Публикация в следующий этап (transfer) ----
    transfer_task = {
        "entity": entity,
        "updated_at": updated_at,
        "period": period,
        "folder_path": folder_path,
        "split_result": split_result,
        "checksum_result": checksum_result,
    }
    await kafka_client.send_message(
        KAFKA_TRANSFER_TOPIC,
        value=transfer_task,
        key=entity,
    )
    logger.info(f"[VERIFICATION] → Опубликовано в {KAFKA_TRANSFER_TOPIC}")
