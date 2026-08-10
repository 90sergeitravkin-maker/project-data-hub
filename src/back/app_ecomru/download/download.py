# src/back/app_ecomru/download/download.py
"""
Модуль для атомарного скачивания файлов с retry-логикой и поддержкой докачки (HTTP Range).

Улучшения:
- HTTP Range: при обрыве связи файл докачивается с места разрыва, а не с нуля.
- Увеличенный chunk_size (1 МБ вместо 8 КБ) — меньше системных вызовов.
- requests.Session — переиспользование TCP-соединений между файлами.
- Корректная обработка IncompleteRead от urllib3.

Стратегия повторных попыток: 1-я попытка сразу, 2-я через 30 сек, 3-я через 60 сек.
"""
import time
import shutil
import requests
from urllib3.exceptions import IncompleteRead
from http.client import IncompleteRead as HttpIncompleteRead

from pathlib import Path
from typing import List, Tuple

from src.core.logger import logger
from src.back.app_ecomru.config import (
    DATA_FILE_TEMP,
    DATA_FILE_RAW,
    DOWNLOAD_TIMEOUT,
    DOWNLOAD_RETRIES,
    DISK_SPACE_SAFETY_FACTOR,
    ECOMRU_CHUNK_SIZE,
)

# Используем 1 МБ для оптимальной производительности при скачивании крупных файлов
CHUNK_SIZE = max(ECOMRU_CHUNK_SIZE, 1024 * 1024)


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


def check_all_links_available(session: requests.Session, links: List[str]) -> int:
    """
    Проверяет доступность каждой ссылки через сессию.
    Возвращает суммарный заявленный размер файлов в байтах.
    """
    total_size = 0
    # Кортеж (connect_timeout, read_timeout): 5 сек на соединение, 30 сек на чтение заголовков
    timeout = (5, 30)

    for url in links:
        try:
            # 1. Пытаемся сделать HEAD-запрос
            resp = session.head(url, timeout=timeout, allow_redirects=True)

            # 2. Fallback: MinIO/S3 и некоторые CDN часто не поддерживают HEAD (405/501)
            if resp.status_code in (405, 501):
                resp = session.get(url, timeout=timeout, stream=True, allow_redirects=True)
                resp.close()  # Сразу закрываем соединение, тело не читаем

            if resp.status_code != 200:
                raise RuntimeError(f"Недоступен: {url} (код {resp.status_code})")

            # 3. Считаем размер
            content_length = resp.headers.get("Content-Length")
            if content_length:
                try:
                    total_size += int(content_length)
                except ValueError:
                    pass

        except requests.exceptions.Timeout:
            # Сервер "тупит" на проверке. Не прерываем задачу, так как реальное
            # скачивание имеет таймаут DOWNLOAD_TIMEOUT (300с) и скачает файл.
            logger.warning(
                f"[DOWNLOAD] Таймаут проверки ссылки: {url}. "
                f"Пропускаем оценку размера, скачивание продолжится."
            )
        except requests.exceptions.RequestException as e:
            # Реальные сетевые ошибки (DNS, отказ в соединении) — прерываем
            raise RuntimeError(f"Ошибка проверки ссылки {url}: {e}")

    return total_size


def _download_file_with_resume(session: requests.Session,
                               url: str,
                               filepath: Path,
                               attempt: int,
                               max_retries: int, ) -> None:
    """
    Скачивает один файл с поддержкой докачки (HTTP Range).

    Если файл уже частично скачан, отправляет заголовок Range и продолжает
    с места обрыва. Если сервер не поддерживает Range (возвращает 200 вместо 206),
    файл перезаписывается с нуля.
    """
    # Определяем, сколько уже скачано
    downloaded_size = filepath.stat().st_size if filepath.exists() else 0
    file_mode = 'ab' if downloaded_size > 0 else 'wb'

    headers = {}
    if downloaded_size > 0:
        headers['Range'] = f'bytes={downloaded_size}-'
        logger.info(
            f"Докачка {filepath.name} с {downloaded_size:,} байт "
            f"(попытка {attempt + 1}/{max_retries})"
        )
    else:
        logger.info(
            f"Скачиваю {filepath.name} с нуля "
            f"(попытка {attempt + 1}/{max_retries}) в {filepath}"
        )

    with session.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT, headers=headers) as r:
        # Если сервер не поддержал Range (вернул 200 вместо 206) —
        # значит он отдаёт файл с начала. Удаляем огрызок и качаем заново.
        if r.status_code == 200 and downloaded_size > 0:
            logger.warning(
                f"Сервер не поддерживает Range для {filepath.name}. "
                f"Перезаписываю файл с нуля."
            )
            filepath.unlink(missing_ok=True)
            file_mode = 'wb'
            downloaded_size = 0

        r.raise_for_status()

        # Проверяем, что сервер поддерживает докачку
        accept_ranges = r.headers.get("Accept-Ranges", "").lower()
        content_length = r.headers.get("Content-Length")
        expected_size = int(content_length) + downloaded_size if content_length else None

        bytes_written = downloaded_size

        with open(filepath, file_mode) as f:
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    bytes_written += len(chunk)

        # Проверка целостности: если сервер заявил размер, проверяем совпадение
        if expected_size and bytes_written < expected_size:
            raise IncompleteRead(
                partial=bytes_written,
                expected=expected_size,
            )


def download_all_files(session: requests.Session, links: List[str], target_dir: Path) -> List[Path]:
    """
    Скачивает все файлы по ссылкам с retry-логикой.
    Делегирует процесс скачивания в _download_file_with_resume для поддержки HTTP Range (докачки).
    """
    downloaded = []
    for url in links:
        filename = Path(url).name
        filepath = target_dir / filename
        success = False
        last_error = None

        for attempt in range(DOWNLOAD_RETRIES):
            try:
                # ← Делегируем скачивание функции с поддержкой докачки
                _download_file_with_resume(
                    session=session,
                    url=url,
                    filepath=filepath,
                    attempt=attempt,
                    max_retries=DOWNLOAD_RETRIES
                )
                success = True
                break

            except requests.exceptions.HTTPError as e:
                # Специальная обработка HTTP 416 (Range Not Satisfiable)
                # Возникает, если локальный "огрызок" оказался больше, чем файл на сервере
                # (например, файл на сервере был обновлен и уменьшен).
                if e.response is not None and e.response.status_code == 416:
                    logger.warning(
                        f"HTTP 416 для {filename}: локальный огрызок невалиден. "
                        f"Удаляю и начинаю с нуля."
                    )
                    if filepath.exists():
                        filepath.unlink()
                    # Не ждём 30 секунд, сразу идём на следующую попытку (которая скачает с нуля)
                    continue

                last_error = e
                logger.warning(
                    f"Ошибка скачивания {filename} (попытка {attempt + 1}/{DOWNLOAD_RETRIES}): {e}"
                )
                if attempt < DOWNLOAD_RETRIES - 1:
                    delay = 30 * (attempt + 1)
                    logger.info(f"Ожидание {delay} секунд перед повторной попыткой...")
                    time.sleep(delay)

            # ← Добавлен отлов IncompleteRead (обрыв связи)
            except (requests.exceptions.RequestException, OSError, IncompleteRead, HttpIncompleteRead) as e:
                last_error = e
                logger.warning(
                    f"Сетевая ошибка / обрыв связи для {filename} "
                    f"(попытка {attempt + 1}/{DOWNLOAD_RETRIES}): {type(e).__name__}"
                )
                if attempt < DOWNLOAD_RETRIES - 1:
                    delay = 30 * (attempt + 1)
                    # Файл частично сохранен, следующая попытка автоматически использует HTTP Range
                    logger.info(f"Ожидание {delay} секунд перед повторной попыткой (докачкой)...")
                    time.sleep(delay)

        if not success:
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
    Перед скачиванием проверяет:
    1. Доступность temp-папки для записи
    2. Доступность raw-папки для записи
    3. Достаточность места на диске

    Использует requests.Session для переиспользования TCP-соединений.
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
    raw_target.parent.mkdir(parents=True, exist_ok=True)

    # ПРОВЕРКА 1: Доступность temp-папки для записи
    if not is_path_writable(temp_target):
        raise PermissionError(f"Нет прав на запись во временную директорию: {temp_target}")
    logger.debug(f"✓ Temp-директория доступна для записи: {temp_target}")

    # ПРОВЕРКА 2: Доступность raw-папки для записи
    if not is_path_writable(raw_target.parent):
        raise PermissionError(f"Нет прав на запись в постоянную директорию: {raw_target.parent}")
    logger.debug(f"✓ Raw-директория доступна для записи: {raw_target.parent}")

    # Создаём сессию для переиспользования соединений
    session = requests.Session()

    try:
        # ПРОВЕРКА 3: Доступность ссылок + оценка размера
        total_size = check_all_links_available(session, links)
        logger.info(
            f"Ссылки доступны ({len(links)} шт.). "
            f"Оценочный размер: {total_size / (1024 * 1024):.1f} MB"
        )

        # ПРОВЕРКА 4: Достаточность места на диске
        if total_size > 0:
            is_enough, free_bytes, required_bytes = is_disk_space_sufficient(
                temp_target, total_size
            )
            free_gb = free_bytes / (1024 ** 3)
            need_gb = required_bytes / (1024 ** 3)

            if not is_enough:
                raise RuntimeError(
                    f"Недостаточно места на диске: "
                    f"свободно {free_gb:.2f} GB, "
                    f"требуется ~{need_gb:.2f} GB (с запасом {DISK_SPACE_SAFETY_FACTOR}x)"
                )
            logger.info(
                f"✓ Место на диске: свободно {free_gb:.2f} GB, "
                f"требуется ~{need_gb:.2f} GB"
            )
        else:
            logger.warning(
                "Content-Length недоступен в заголовках — "
                "проверка места на диске пропущена"
            )

        # ── Скачивание и перемещение ──
        downloaded = []
        try:
            downloaded = download_all_files(session, links, temp_target)
            move_temp_to_raw(temp_target, raw_target)
            moved_files = list(raw_target.glob("*.*"))
            logger.info(f"Перемещено файлов: {len(moved_files)}")
            return moved_files
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            cleanup_temp(downloaded, temp_target)
            raise RuntimeError(f"Скачивание прервано, ничего не сохранено: {e}") from e

    finally:
        session.close()


def is_path_writable(path: Path) -> bool:
    """
    Проверяет, доступна ли директория для записи.
    Создаёт тестовый файл и сразу удаляет его.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".write_test_tmp"
        test_file.touch()
        test_file.unlink()
        return True
    except (OSError, PermissionError) as e:
        logger.warning(f"[DOWNLOAD] Проверка записи провалена для {path}: {e}")
        return False


def get_disk_free_space(path: Path) -> int:
    """Возвращает свободное место в байтах. Если ошибка — 0."""
    try:
        usage = shutil.disk_usage(str(path))
        return usage.free
    except (OSError, ValueError):
        return 0


def is_disk_space_sufficient(path: Path, required_bytes: int) -> Tuple[bool, int, int]:
    """
    Проверяет, достаточно ли места на диске.

    Логика: требуется (required_bytes + safety_factor) байт.

    Returns:
        (достаточно_ли, свободно_байт, требуется_байт_с_запасом)
    """
    free_bytes = get_disk_free_space(path)
    required_with_margin = required_bytes + DISK_SPACE_SAFETY_FACTOR
    return free_bytes >= required_with_margin, free_bytes, required_with_margin
