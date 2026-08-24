# src/back/app_data_validator/services.py
import json
from pathlib import Path
from typing import Dict, Any

from src.core.logger import logger
from src.back.app_data_validator.validator import DataValidator

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

class ValidationService:
    @staticmethod
    def validate_file(file_path: str, source_name: str) -> Dict[str, Any]:
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

        if source_name not in config:
            available = ", ".join(sorted(config.keys()))
            return {"error": f"Источник '{source_name}' не найден. Доступные: {available}"}

        source_config = config[source_name]

        # Извлекаем секцию 'column'
        if isinstance(source_config, dict) and 'column' in source_config:
            column_rules = source_config['column']
        elif isinstance(source_config, dict):
            column_rules = source_config
        else:
            return {"error": f"Источник '{source_name}' не содержит правил валидации"}

        # Преобразуем is_true -> required
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