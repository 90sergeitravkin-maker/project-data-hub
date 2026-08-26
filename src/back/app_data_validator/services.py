# src/back/app_data_validator/services.py
import json
from pathlib import Path
from typing import Dict, Any, Optional
from src.core.logger import logger
from src.back.app_data_validator.validator import DataValidator
from src.back.app_data_validator.config import (
    KAFKA_VALIDATION_OUTPUT_TOPIC,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _normalize_keys(obj):
    """Рекурсивно убирает пробелы по краям всех ключей и строковых значений."""
    if isinstance(obj, dict):
        return {k.strip(): _normalize_keys(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_normalize_keys(item) for item in obj]
    elif isinstance(obj, str):
        return obj.strip()
    return obj


def _extract_source_from_path(file_path: str, config: dict) -> Optional[str]:
    """Извлекает имя источника из начала пути."""
    normalized_path = file_path.replace('\\', '/').strip('/')
    parts = normalized_path.split('/')
    if not parts:
        return None
    first_part = parts[0]
    if first_part in config:
        return first_part
    first_part_lower = first_part.lower()
    for source in config.keys():
        if source.lower() == first_part_lower:
            return source
    for source in config.keys():
        if source in normalized_path:
            return source
    return None


class ValidationService:
    @staticmethod
    def validate_file(file_path: str) -> Dict[str, Any]:
        """
        Валидация файла или директории.
        """
        config_path = PROJECT_ROOT / "files" / "_fields_config.json"
        if not config_path.exists():
            return {"error": f"Конфигурация не найдена: {config_path}"}
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                raw_config = json.load(f)
        except Exception as e:
            logger.error(f"[ValidationService] Ошибка чтения конфигурации: {e}")
            return {"error": f"Ошибка чтения конфигурации: {e}"}

        config = _normalize_keys(raw_config)
        source_name = _extract_source_from_path(file_path, config)
        if source_name is None:
            return {
                "error": f"Не удалось определить источник из пути: {file_path}",
                "available_sources": list(config.keys()),
                "hint": "Убедитесь, что путь начинается с имени источника из конфигурации"
            }

        logger.info(f"[ValidationService] Автоматически определён источник: {source_name} из пути {file_path}")

        if source_name not in config:
            available = ", ".join(sorted(config.keys()))
            return {
                "error": f"Источник '{source_name}' не найден в конфигурации",
                "available_sources": list(config.keys()),
                "hint": f"Доступные источники: {available}"
            }

        source_config = config[source_name]
        if isinstance(source_config, dict) and 'column' in source_config:
            column_rules = source_config['column']
        elif isinstance(source_config, dict):
            column_rules = source_config
        else:
            return {
                "error": f"Источник '{source_name}' не содержит правил валидации",
                "hint": "Проверьте структуру конфигурации."
            }

        for col_name, col_rules in column_rules.items():
            if isinstance(col_rules, dict) and 'is_true' in col_rules and 'required' not in col_rules:
                col_rules['required'] = bool(col_rules.pop('is_true'))

        validator_config = {source_name: column_rules}
        try:
            validator = DataValidator(validator_config, max_error_examples=1000, max_duplicate_examples=10)
            return validator.validate_file(file_path, source_name)
        except Exception as e:
            logger.error(f"[ValidationService] Ошибка валидации: {e}", exc_info=True)
            return {"error": f"Ошибка валидации: {e}"}

    # ================================================================
    # KAFKA ОБРАБОТЧИК
    # ================================================================
    @classmethod
    async def handle_validation_task(cls, task: Dict[str, Any]) -> None:
        """
        Обработчик Kafka-сообщений из топика ecomru-verification.
        Читает результат скачивания, запускает валидацию,
        публикует результат в ecomru-validation.
        """
        from src.core.kafka import kafka_client

        task_id = task.get("task_id", "unknown")
        entity = task.get("entity", "")
        folder_path = task.get("folder_path", "")
        download_result = task.get("download_result", {})
        download_status = download_result.get("status", "unknown")

        logger.info(
            f"[VALIDATOR] Получена задача: task_id={task_id}, "
            f"entity={entity}, folder={folder_path}, "
            f"download_status={download_status}"
        )

        # Если скачивание упало — пропускаем валидацию, но пишем результат
        if download_status == "error":
            logger.warning(
                f"[VALIDATOR] Пропуск валидации: скачивание завершилось с ошибкой "
                f"(task_id={task_id})"
            )
            validation_result = {
                "task_id": task_id,
                "entity": entity,
                "folder_path": folder_path,
                "status": "skipped",
                "reason": "download_failed",
                "download_errors": download_result.get("errors", []),
            }
            await kafka_client.send_message(
                KAFKA_VALIDATION_OUTPUT_TOPIC,
                value=validation_result,
                key=entity,
            )
            logger.info(
                f"[VALIDATOR] → Результат (skipped) опубликован в "
                f"{KAFKA_VALIDATION_OUTPUT_TOPIC}"
            )
            return

        # Если нет folder_path — нечего валидировать
        if not folder_path:
            logger.warning(f"[VALIDATOR] Нет folder_path в задаче {task_id}")
            return

        # Запускаем валидацию (синхронный вызов в отдельном потоке)
        import asyncio
        try:
            result = await asyncio.to_thread(cls.validate_file, folder_path)
        except Exception as e:
            logger.error(f"[VALIDATOR] Критическая ошибка валидации: {e}", exc_info=True)
            result = {"error": str(e)}

        # Формируем итоговое сообщение
        if "error" in result:
            validation_status = "failed"
        elif result.get("status") == "OK":
            validation_status = "passed"
        else:
            validation_status = "failed"

        validation_message = {
            "task_id": task_id,
            "entity": entity,
            "updated_at": task.get("updated_at", ""),
            "period": task.get("period", ""),
            "folder_path": folder_path,
            "status": validation_status,
            "validation_result": result,
        }

        # Публикуем результат в выходной топик
        await kafka_client.send_message(
            KAFKA_VALIDATION_OUTPUT_TOPIC,
            value=validation_message,
            key=entity,
        )
        logger.info(
            f"[VALIDATOR] → Результат ({validation_status}) опубликован в "
            f"{KAFKA_VALIDATION_OUTPUT_TOPIC} (task_id={task_id})"
        )
