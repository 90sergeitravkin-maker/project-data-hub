# src/core/data_checker.py
"""
Общий сервис проверки наличия данных и извлечения дат.
Переиспользуется всеми приложениями проекта.
"""
import re
from pathlib import Path
from typing import List, Tuple, Dict, Any, Set, Optional
from src.core.logger import logger


class DataChecker:
    """
    Общий сервис для проверки папок и извлечения метаданных.
    Переиспользуется в app_file_manager, app_macmap, app_groups и других модулях.
    """

    DEFAULT_DATE_PATTERN: str = r'^\d{4}-\d{2}-\d{2}$'  # YYYY-MM-DD

    @staticmethod
    def _has_files_recursive(folder_path: Path) -> bool:
        """Рекурсивно проверяет наличие файлов в папке и подпапках."""
        if not folder_path.exists() or not folder_path.is_dir():
            return False
        try:
            for item in folder_path.iterdir():
                if item.is_file():
                    return True
                if item.is_dir() and DataChecker._has_files_recursive(item):
                    return True
        except PermissionError:
            logger.warning(f"Нет прав доступа: {folder_path}")
            return False
        except Exception as e:
            logger.error(f"Ошибка обхода: {e}")
            return False
        return False

    @staticmethod
    async def check_data_list(
            base_url: Path,
            folders: Optional[List[str]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Проверяет наличие папок и файлов в них (рекурсивно).

        Args:
            base_url: Базовый путь к данным
            folders: Список имён папок для проверки (может быть None)

        Returns:
            Tuple[bool, Dict]:
                success: True если все проверки пройдены
                result: {
                    'missing': [отсутствующие папки],
                    'empty': [пустые папки],
                    'found': [папки с файлами],
                    'error': 'сообщение' (при критической ошибке)
                }
        """
        if not folders:
            logger.warning("[DataChecker] Параметр 'folders' пуст или None")
            return False, {
                'missing': [],
                'empty': [],
                'found': [],
                'error': 'folders list is empty or None'
            }

        # Нормализация: фильтруем пустые строки и дубликаты
        folders = list(dict.fromkeys(f.strip() for f in folders if f and f.strip()))
        if not folders:
            return False, {
                'missing': [],
                'empty': [],
                'found': [],
                'error': 'no valid folders after normalization'
            }

        missing = []
        empty = []
        found = []

        if not base_url or not base_url.exists() or not base_url.is_dir():
            logger.error(f"[DataChecker] Базовый путь невалиден: {base_url}")
            return False, {
                'missing': folders,
                'empty': [],
                'found': [],
                'error': f'base_path_invalid: {base_url}'
            }

        for folder in folders:
            full_path = base_url / folder
            try:
                if not full_path.exists():
                    missing.append(folder)
                    continue
                if not full_path.is_dir():
                    missing.append(folder)
                    continue
                has_files = DataChecker._has_files_recursive(full_path)
                if not has_files:
                    empty.append(folder)
                else:
                    found.append(folder)
            except PermissionError:
                missing.append(folder)
            except Exception as e:
                logger.error(f"Ошибка проверки '{folder}': {e}")
                missing.append(folder)

        success = len(missing) == 0 and len(empty) == 0
        result = {
            'missing': missing,
            'empty': empty,
            'found': found,
            'total_checked': len(folders),
            'base_path': str(base_url)
        }

        if missing:
            logger.error(f"[DataChecker] Не найдено папок: {missing}")
        if empty:
            logger.warning(f"[DataChecker] Пустые папки: {empty}")
        if found:
            logger.info(f"[DataChecker] Найдено файлов в папках: {found}")

        return success, result

    @staticmethod
    async def extract_dates_from_folders(
            base_url: Path,
            subfolder: str,
            date_pattern: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Извлекает даты из имён подпапок."""
        pattern = date_pattern or DataChecker.DEFAULT_DATE_PATTERN
        result = {
            'dates': [],
            'total': 0,
            'path': str(base_url / subfolder),
            'error': None
        }

        target_path = base_url / subfolder
        if not target_path.exists():
            result['error'] = f"Папка не найдена: {subfolder}"
            return False, result
        if not target_path.is_dir():
            result['error'] = f"Не является папкой: {subfolder}"
            return False, result

        dates = set()
        date_regex = re.compile(pattern)
        try:
            for item in target_path.iterdir():
                if item.is_dir() and date_regex.match(item.name):
                    dates.add(item.name)
        except PermissionError:
            result['error'] = "Нет прав доступа"
            return False, result
        except Exception as e:
            result['error'] = f"Ошибка: {str(e)}"
            return False, result

        sorted_dates = sorted(dates)
        result['dates'] = sorted_dates
        result['total'] = len(sorted_dates)
        return True, result

    @staticmethod
    def validate_dataset(dataset: str) -> Tuple[bool, Optional[str]]:
        """Закладка на валидацию папки."""
        return True, None
