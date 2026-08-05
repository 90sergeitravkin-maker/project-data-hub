# src/back/app_ecomru/download/download.py
"""
Модуль для атомарного скачивания файлов с retry-логикой.
Стратегия повторных попыток: 1-я попытка сразу, 2-я через 30 сек, 3-я через 60 сек.
"""
import time
import shutil
import requests

from pathlib import Path
from typing import List, Tuple
from src.core.logger import logger
from src.back.app_ecomru.config import (
    DATA_FILE_TEMP,
    DATA_FILE_RAW,
    DOWNLOAD_TIMEOUT,
    DOWNLOAD_RETRIES,
)


def build_paths(data: dict, temp_root: Path, raw_root: Path) -> Tuple[Path, Path, Path]:
    """Строит пути для временной и постоянной папки на основе данных задачи."""
    parts = [
        part for part in (
            data.get("entity", ""),
            data.get("updated_at", ""),
            data.get("period", "")
        ) if part
    ]
    rel_path = Path(*parts) if parts else Path(".")
    return (
        temp_root / rel_path,
        raw_root / rel_path,
        rel_path
    )


def check_all_links_available(links: List[str]) -> None:
    """Проверяет доступность каждой ссылки через HEAD-запрос."""
    for url in links:
        resp = requests.head(url, timeout=10)
        if resp.status_code != 200:
            raise RuntimeError(f"Недоступен: {url} (код {resp.status_code})")


def download_all_files(links: List[str], target_dir: Path) -> List[Path]:
    """
    Скачивает все файлы по ссылкам с retry-логикой.

    Стратегия повторных попыток:
    - 1-я попытка: сразу
    - 2-я попытка: через 30 секунд
    - 3-я попытка: через 60 секунд (30 * (attempt + 1))

    Args:
        links: Список URL-адресов для скачивания.
        target_dir: Папка, куда будут сохранены файлы.
    Returns:
        Список путей к скачанным файлам.
    """
    downloaded = []

    for url in links:
        filename = Path(url).name
        filepath = target_dir / filename

        success = False
        last_error = None

        for attempt in range(DOWNLOAD_RETRIES):
            try:
                logger.info(
                    f"Скачиваю {filename} (попытка {attempt + 1}/{DOWNLOAD_RETRIES}) в {filepath}"
                )

                with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT) as r:
                    r.raise_for_status()
                    with open(filepath, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                # Успех - выходим из цикла попыток
                success = True
                break

            except (requests.exceptions.RequestException, OSError) as e:
                last_error = e
                logger.warning(
                    f"Ошибка скачивания {filename} (попытка {attempt + 1}/{DOWNLOAD_RETRIES}): {e}"
                )

                # Если это не последняя попытка - ждём перед следующей
                if attempt < DOWNLOAD_RETRIES - 1:
                    delay = 30 * (attempt + 1)  # 30, 60, 90... секунд
                    logger.info(f"Ожидание {delay} секунд перед повторной попыткой...")
                    time.sleep(delay)

        if not success:
            # Все попытки исчерпаны
            logger.error(
                f"Не удалось скачать файл {filename} после {DOWNLOAD_RETRIES} попыток. "
                f"Последняя ошибка: {last_error}"
            )
            raise RuntimeError(
                f"Не удалось скачать файл {url} после {DOWNLOAD_RETRIES} попыток: {last_error}"
            )

        downloaded.append(filepath)

    return downloaded


def move_temp_to_raw(temp_target: Path, raw_target: Path) -> None:
    """Перемещает содержимое временной папки в постоянную."""
    logger.info(f"Перемещаем {temp_target} -> {raw_target}")
    if raw_target.exists():
        logger.info(f"Удаляем существующую {raw_target}")
        shutil.rmtree(raw_target)
    shutil.copytree(temp_target, raw_target)
    shutil.rmtree(temp_target)
    files = list(raw_target.iterdir())
    if not files:
        raise RuntimeError("Целевая папка пуста после копирования")
    logger.info(f"В целевой папке найдены файлы: {[f.name for f in files]}")


def cleanup_temp(downloaded: List[Path], temp_target: Path) -> None:
    """Удаляет скачанные файлы и временную папку, если она пуста."""
    for file_path in downloaded:
        if file_path.exists():
            file_path.unlink()
    if temp_target.exists() and not any(temp_target.iterdir()):
        temp_target.rmdir()


def download_and_move_atomically(data: dict) -> List[Path]:
    """
    Выполняет атомарное скачивание и перемещение с retry-логикой.
    Возвращает список путей к перемещённым файлам.
    """
    temp_root = Path(DATA_FILE_TEMP) if DATA_FILE_TEMP else Path(".")
    raw_root = Path(DATA_FILE_RAW) if DATA_FILE_RAW else Path(".")
    temp_target, raw_target, _ = build_paths(data, temp_root, raw_root)
    links = data.get("links", [])
    if not isinstance(links, list) or not links:
        raise ValueError("Нет ссылок для скачивания")

    logger.debug(f"Временная папка: {temp_target}")
    logger.debug(f"Постоянная папка: {raw_target}")
    temp_target.mkdir(parents=True, exist_ok=True)

    check_all_links_available(links)
    downloaded = []

    try:
        downloaded = download_all_files(links, temp_target)
        move_temp_to_raw(temp_target, raw_target)
        moved_files = list(raw_target.glob("*.*"))
        logger.info(f"Перемещено файлов: {len(moved_files)}")
        return moved_files
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        cleanup_temp(downloaded, temp_target)
        raise RuntimeError(f"Скачивание прервано, ничего не сохранено: {e}") from e
