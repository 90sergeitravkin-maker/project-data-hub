# src/back/app_ecomru/services.py
import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from src.core.logger import logger
from src.core.kafka import kafka_client, InvalidMessageError
from src.back.app_ecomru.config import (
    KAFKA_TRANSFER_TOPIC,
    KAFKA_VERIFICATION_TOPIC,
    KAFKA_REPORT_TOPIC,
    get_split_columns,
)
from src.back.app_ecomru.download.download import download_and_move_atomically
from src.back.app_datasets.services import DataSetsVerifiedServices
from src.back.app_link.services import Link
from src.back.app_ecomru.schemas import PipelineReport, DownloadResult, ProcessingResult


async def _save_links_to_app_link(urls: list[str]) -> None:
    """Сохраняет ссылки в app_link (без изменений)."""
    if not urls:
        return
    try:
        result = await Link.process_links(urls)
        new_count = sum(1 for r in result.results if r.status == "new")
        dup_count = sum(1 for r in result.results if r.status == "duplicate")
        logger.info(f"[DOWNLOAD] app_link: новых={new_count}, дубликатов={dup_count}")
    except Exception as e:
        logger.error(f"[DOWNLOAD] Ошибка сохранения в app_link: {e}", exc_info=True)


def _resolve_split_columns(task: Dict[str, Any], entity: str) -> List[str]:
    """
    Определяет список столбцов разбиения.
    Приоритет: split_column/split_columns из сообщения → конфиг по entity (hot-reload).
    """
    # 1. Из сообщения: split_columns (список)
    raw_list = task.get("split_columns")
    if isinstance(raw_list, list) and raw_list:
        return [c for c in raw_list if isinstance(c, str) and c]

    # 2. Из сообщения: split_column (строка)
    raw_single = task.get("split_columns")
    if isinstance(raw_single, str) and raw_single:
        return [raw_single]

    # 3. Из конфига по entity (hot-reload)
    return get_split_columns(entity)


# ============================================================
# ЭТАП 1: СКАЧИВАНИЕ → авто-переход к обработке
# ============================================================
async def handle_download_task(task: Dict[str, Any]) -> None:
    """
    Обработчик задач из топика 'ecomru-download'.
    """
    started_at = datetime.now(timezone.utc)
    task_id = task.get("task_id") or str(uuid.uuid4())

    # ---- Адаптация формата (старый/новый) ----
    if "url" in task and "relative_path" in task:
        urls = task["url"] if isinstance(task["url"], list) else [task["url"]]
        rel_path = Path(task["relative_path"])
        parts = rel_path.parts
        entity = parts[0] if len(parts) > 0 else task.get("entity", "")
        updated_at = parts[1] if len(parts) > 1 else task.get("updated_at", "")
        period = parts[2] if len(parts) > 2 else task.get("period", "")
    else:
        urls = task.get("urls", [])
        dest_path = task.get("dest_path", "").strip("/")
        if not urls:
            raise InvalidMessageError(f"[DOWNLOAD] Нет URL для скачивания: {task}")
        parts = Path(dest_path).parts
        entity = parts[0] if len(parts) > 0 else task.get("entity", "")
        updated_at = parts[1] if len(parts) > 1 else task.get("updated_at", "")
        period = parts[2] if len(parts) > 2 else task.get("period", "")

    # Столбцы разбиения: из сообщения или из конфига (hot-reload)
    split_columns = _resolve_split_columns(task, entity)

    data = {
        "entity": entity,
        "updated_at": updated_at,
        "period": period,
        "links": urls,
    }

    logger.info(f"[DOWNLOAD] Получена задача: task_id={task_id}, entity={entity}, "
                f"files={len(urls)}, split_columns={split_columns or 'НЕТ'}")

    # ---- Скачивание ----
    download_errors: List[str] = []
    moved_files: List[Path] = []
    download_status = "completed"

    try:
        moved_files = await asyncio.to_thread(download_and_move_atomically, data)
        logger.info(f"[DOWNLOAD] ✅ Скачано файлов: {len(moved_files)}")
    except Exception as e:
        logger.error(f"[DOWNLOAD] ❌ Ошибка скачивания: {e}", exc_info=True)
        download_errors.append(str(e))
        download_status = "error"
        # НЕ делаем raise! Передаём ошибку в verification, чтобы Airflow получил отчёт.

    # ---- Сохранение метаданных (только если есть файлы) ----
    for file_path in moved_files:
        try:
            await DataSetsVerifiedServices.save_file_metadata(
                file_path, entity=entity, period=period, updated_at=updated_at
            )
        except Exception as e:
            logger.error(f"[DOWNLOAD] Ошибка метаданных {file_path.name}: {e}")

    if not download_errors:
        await _save_links_to_app_link(data.get("links", []))

    # ---- ПУБЛИКАЦИЯ В СЛЕДУЮЩИЙ ЭТАП (verification) ----
    finished_at = datetime.now(timezone.utc)
    folder_path = f"{entity}/{updated_at}/{period}"

    verification_task = {
        "task_id": task_id,
        "entity": entity,
        "updated_at": updated_at,
        "period": period,
        "folder_path": folder_path,
        "split_columns": split_columns,  # список столбцов (может быть пустым)
        "download_result": {
            "status": download_status,
            "files_downloaded": len(moved_files),
            "files_failed": max(0, len(urls) - len(moved_files)),
            "total_size_bytes": sum(f.stat().st_size for f in moved_files if f.exists()),
            "duration_sec": (finished_at - started_at).total_seconds(),
            "file_paths": [str(f) for f in moved_files],
            "errors": download_errors,
        },
        "started_at": started_at.isoformat(),
    }

    await kafka_client.send_message(
        KAFKA_VERIFICATION_TOPIC,
        value=verification_task,
        key=entity,
    )
    logger.info(f"[DOWNLOAD] → Опубликовано в {KAFKA_VERIFICATION_TOPIC} "
                f"(task_id={task_id}, status={download_status})")


# ============================================================
# ЭТАП 2: ОБРАБОТКА (разбиение) → отчёт
# ============================================================
async def handle_verification_task(task: Dict[str, Any]) -> None:
    """
    Этап 2: Обработка файлов и формирование итогового отчёта для Airflow.
    Отчёт отправляется ВСЕГДА, даже если на предыдущих шагах были ошибки.
    """
    task_id = task.get("task_id") or str(uuid.uuid4())
    folder_path = task.get("folder_path")
    entity = task.get("entity", "")
    updated_at = task.get("updated_at", "")
    period = task.get("period", "")
    download_result_data = task.get("download_result", {})
    pipeline_started_at = task.get("started_at", datetime.now(timezone.utc).isoformat())

    # Столбцы разбиения: из задачи или из конфига (hot-reload)
    split_columns = _resolve_split_columns(task, entity)
    split_columns_str = ", ".join(split_columns) if split_columns else None

    if not folder_path or not isinstance(folder_path, str):
        raise InvalidMessageError(
            f"[VERIFICATION] Невалидное сообщение: отсутствует folder_path. task={task}"
        )

    logger.info(
        f"[VERIFICATION] Получена задача: task_id={task_id}, folder={folder_path}, "
        f"columns={split_columns or 'НЕ УКАЗАНЫ (пропуск разбиения)'}"
    )

    processing_result = ProcessingResult(status="skipped", split_performed=False)
    processing_error = None

    # Если скачивание уже упало, пропускаем разбиение
    if download_result_data.get("status") == "error":
        processing_result = ProcessingResult(
            status="skipped",
            split_performed=False,
            errors=["Пропущено из-за ошибки скачивания"],
        )
    elif split_columns:
        try:
            # Импорт внутри функции, чтобы избежать циклических импортов
            from src.back.app_ecomru.split_data.services import process_data_folder

            # Передаём СПИСОК столбцов
            result = await asyncio.to_thread(process_data_folder, folder_path, split_columns)
            status = result.get("status")

            if status == "error":
                processing_result = ProcessingResult(
                    status="error",
                    split_column=split_columns_str,
                    errors=[result.get("error", "Unknown error")],
                )
                processing_error = result.get("error", "Unknown error")
            elif status == "empty":
                logger.warning(f"[VERIFICATION] Нет файлов: {result.get('message')}")
                processing_result = ProcessingResult(
                    status="completed",
                    split_column=split_columns_str,
                    split_performed=False,
                )
            else:
                split_result = result.get("split_result", {})
                checksum_result = result.get("checksum_result", {})

                processing_result = ProcessingResult(
                    status="completed",
                    split_performed=True,
                    split_column=split_columns_str,
                    unique_values=split_result.get("unique_values", 0),
                    total_rows=split_result.get("total_rows", 0),
                    output_files_count=sum(
                        info.get("num_parts", 0)
                        for info in split_result.get("details", {}).values()
                    ),
                    output_dir=split_result.get("output_dir"),
                    checksum_result=checksum_result,
                )

                logger.info(
                    f"[VERIFICATION] ✅ Разбиение завершено: "
                    f"групп={processing_result.unique_values}, "
                    f"строк={processing_result.total_rows}"
                )

                transfer_task = {
                    "task_id": task_id,
                    "entity": entity,
                    "updated_at": updated_at,
                    "period": period,
                    "folder_path": folder_path,
                    "split_columns": split_columns,
                    "split_result": split_result,
                    "checksum_result": checksum_result,
                }
                await kafka_client.send_message(
                    KAFKA_TRANSFER_TOPIC, value=transfer_task, key=entity
                )

        except Exception as e:
            logger.error(f"[VERIFICATION] Ошибка: {e}", exc_info=True)
            processing_result = ProcessingResult(
                status="error",
                split_column=split_columns_str,
                errors=[str(e)],
            )
            processing_error = str(e)
    else:
        logger.info(f"[VERIFICATION] split_columns не указаны — разбиение пропущено")
        processing_result = ProcessingResult(
            status="completed",
            split_performed=False,
            split_column=None,
        )

    # ---- ФОРМИРОВАНИЕ ИТОГОВОГО ОТЧЁТА → ecomru-report (ВСЕГДА, даже при ошибке) ----
    finished_at = datetime.now(timezone.utc)
    try:
        started_dt = datetime.fromisoformat(pipeline_started_at) if isinstance(pipeline_started_at,
                                                                               str) else pipeline_started_at
    except (ValueError, TypeError):
        started_dt = finished_at

    dl_status = download_result_data.get("status", "completed")
    proc_status = processing_result.status

    if dl_status == "completed" and proc_status == "completed":
        pipeline_status = "completed"
    elif "error" in (dl_status, proc_status):
        pipeline_status = "failed"
    else:
        pipeline_status = "partial"

    report = PipelineReport(
        task_id=task_id,
        entity=entity,
        period=period,
        updated_at=updated_at,
        pipeline_status=pipeline_status,
        download=DownloadResult(**download_result_data) if download_result_data else DownloadResult(status="unknown"),
        processing=processing_result,
        started_at=pipeline_started_at if isinstance(pipeline_started_at, str) else started_dt.isoformat(),
        finished_at=finished_at.isoformat(),
        duration_sec=(finished_at - started_dt).total_seconds(),
    )

    await kafka_client.send_message(
        KAFKA_REPORT_TOPIC,
        value=report.model_dump(),
        key=entity,
    )
    logger.info(
        f"[VERIFICATION] → Отчёт опубликован в {KAFKA_REPORT_TOPIC} "
        f"(task_id={task_id}, status={pipeline_status})"
    )

    # ---- Обработка ошибок для Kafka (DLQ/Retry) ----
    if processing_error:
        logger.error(f"[VERIFICATION] Задача завершена с ошибкой: {processing_error}")
        # raise RuntimeError(f"[VERIFICATION] Ошибка обработки: {processing_error}")