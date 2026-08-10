# send_to_kafka.py
"""
Отправка задач скачивания в Kafka-топик ecomru-download.
Использует HTTP API микросервиса app_kafka (POST /api/v1/app_kafka/produce).

Формат сообщений совместим с handle_download_task
(src/back/app_ecomru/services.py).

Запуск из корня проекта:
  python send_to_kafka.py                     # все записи, формат new
  python send_to_kafka.py --format old        # legacy формат
  python send_to_kafka.py --limit 3           # первые 3 записи
  python send_to_kafka.py --dry-run           # без отправки
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asyncio
import argparse
import httpx
import json
import uuid
import sys

from pathlib import Path
from typing import List, Dict, Any

from src.core.logger import logger
from src.back.app_ecomru.config import (
    KAFKA_DOWNLOAD_TOPIC,
    APP_KAFKA_URL,
)

print(f"KAFKA_DOWNLOAD_TOPIC={KAFKA_DOWNLOAD_TOPIC}")
print(f"APP_KAFKA_URL={APP_KAFKA_URL}")
DATA_FILE = Path("files/comtrade.json")


# Формирование сообщений
def build_message_new(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Новый формат для handle_download_task:
    {"task_id", "urls", "dest_path", "entity", "updated_at", "period"}
    """
    entity = item.get("entity", "")
    updated_at = item.get("updated_at", "")
    period = item.get("period", "")

    parts = [p for p in (entity, updated_at, period) if p]
    dest_path = "/".join(parts) if parts else "."

    return {
        "task_id": str(uuid.uuid4()),
        "urls": item.get("links", []),
        "dest_path": dest_path,
        "entity": entity,
        "updated_at": updated_at,
        "period": period,
    }


def build_message_old(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Старый (legacy) формат для handle_download_task:
    {"url", "relative_path", "entity", "updated_at", "period"}
    """
    entity = item.get("entity", "")
    updated_at = item.get("updated_at", "")
    period = item.get("period", "")

    parts = [p for p in (entity, updated_at, period) if p]
    relative_path = "/".join(parts) if parts else "."

    return {
        "url": item.get("links", []),
        "relative_path": relative_path,
        "entity": entity,
        "updated_at": updated_at,
        "period": period,
    }


async def send_via_http(messages: List[Dict[str, Any]], topic: str) -> int:
    """
    Отправка через POST /api/v1/app_kafka/produce
    """
    sent = 0

    # Формируем URL. Если APP_KAFKA_URL уже содержит путь, просто добавляем /produce
    if "/api/v1/app_kafka" in APP_KAFKA_URL:
        url = f"{APP_KAFKA_URL.rstrip('/')}/produce"
    else:
        url = f"{APP_KAFKA_URL.rstrip('/')}/api/v1/app_kafka/produce"

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, msg in enumerate(messages, 1):
            key = msg.get("task_id") or msg.get("entity")
            payload = {"topic": topic, "value": msg, "key": key}
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                print(
                    f"✅ [{i}/{len(messages)}] → topic={data.get('topic')}"
                    f"partition={data.get('partition')}  offset={data.get('offset')}"
                )
                sent += 1
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"  ❌ [{i}/{len(messages)}] HTTP {e.response.status_code}: {e.response.text}"
                )
            except Exception as e:
                logger.error(f"  ❌ [{i}/{len(messages)}] {type(e).__name__}: {e}")

    return sent


def main():
    parser = argparse.ArgumentParser(
        description="Отправка задач скачивания в Kafka через HTTP API app_kafka"
    )
    parser.add_argument(
        "--file", type=str,
        default=str(DATA_FILE),
        help=f"Путь к JSON-файлу (default: {DATA_FILE})",
    )
    parser.add_argument(
        "--format", choices=["new", "old"],
        default="new",
        help="Формат: new (task_id+urls+dest_path) или old (url+relative_path)",
    )
    parser.add_argument(
        "--topic", type=str,
        default=KAFKA_DOWNLOAD_TOPIC,
        help=f"Топик (default: {KAFKA_DOWNLOAD_TOPIC})",
    )
    parser.add_argument(
        "--limit", type=int,
        default=None,
        help="Отправить только первые N записей",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Только вывести сообщения без отправки",
    )
    args = parser.parse_args()

    # ── Чтение данных ──
    data_path = Path(args.file)
    if not data_path.exists():
        logger.error(f"Файл не найден: {data_path}")
        sys.exit(1)

    with open(data_path, "r", encoding="utf-8-sig") as f:
        items = json.load(f)

    if not isinstance(items, list):
        logger.error("Ожидался JSON-массив")
        sys.exit(1)

    if args.limit:
        items = items[: args.limit]

    print(f"📂 Файл:    {data_path}")
    print(f"📊 Записей: {len(items)}")
    print(f"📡 Формат:  {args.format}")
    print(f"📮 Topic:   {args.topic}")
    print(f"🔗 API URL: {APP_KAFKA_URL}")
    print(f"📤 Метод:   HTTP API (POST /api/v1/app_kafka/produce)")

    # ── Формирование сообщений ──
    builder = build_message_new if args.format == "new" else build_message_old
    messages = []
    for item in items:
        links = item.get("links", [])
        if not links:
            logger.warning(f"  ⚠ Пропуск записи без ссылок: entity={item.get('entity')}")
            continue
        messages.append(builder(item))

    if not messages:
        logger.error("Нет валидных записей для отправки")
        sys.exit(1)

    # ── DRY RUN ──
    if args.dry_run:
        print(f"\n{'=' * 60}")
        print(f"  DRY RUN — отправка не выполняется")
        print(f"  Сообщений: {len(messages)}")
        print(f"{'=' * 60}\n")
        for i, msg in enumerate(messages, 1):
            print(f"  [{i}/{len(messages)}]")
            print(f"    {json.dumps(msg, ensure_ascii=False, indent=4)}")
        return

    # ── Отправка ──
    sent = asyncio.run(send_via_http(messages, args.topic))

    print(f"\n{'=' * 60}")
    print(f"  Итого: {sent}/{len(messages)} сообщений → '{args.topic}'")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
