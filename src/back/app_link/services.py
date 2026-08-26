# src/back/app_link/models.py
import hashlib
import httpx

from typing import List, Set, Tuple
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from src.core.logger import logger
from src.database.manager import DBManager
from src.back.app_link.config import config, KAFKA_TOPIC_LINKS, APP_KAFKA_URL
from src.back.app_link.schemas import LinkStatus, LinkCheckResponse


class Link:
    """
    Модель для работы со ссылками.
    Содержит всю логику нормализации, хеширования, проверки, вставки в БД и отправки в Kafka.
    """
    DB_ALIAS = config.db_alias

    @staticmethod
    def normalize_url(url: str) -> str:
        """Нормализует URL."""
        url = url.strip()
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.lower()
        params = parsed.params.lower() if parsed.params else ''
        if parsed.query:
            query_dict = parse_qs(parsed.query, keep_blank_values=True)
            sorted_items = sorted(
                (k.lower(), [v.lower() for v in vals])
                for k, vals in query_dict.items()
            )
            query = urlencode(sorted_items, doseq=True)
        else:
            query = ''
        fragment = parsed.fragment.lower() if parsed.fragment else ''
        return urlunparse((scheme, netloc, path, params, query, fragment))

    @staticmethod
    def hash_url(normalized: str) -> str:
        """SHA256 хеш нормализованного URL."""
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    @classmethod
    def prepare_urls(cls, urls: List[str]) -> List[Tuple[str, str, str]]:
        """Возвращает список (original, normalized, hash)."""
        return [(url, cls.normalize_url(url), cls.hash_url(cls.normalize_url(url))) for url in urls]

    @classmethod
    async def init_table(cls) -> None:
        """Создаёт таблицу, если не существует."""
        db = DBManager()
        await db.execute(
            cls.DB_ALIAS,
            """
            CREATE TABLE IF NOT EXISTS app_link.links (
                 id             SERIAL    PRIMARY KEY
                ,created_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                ,url            TEXT      NOT NULL
                ,url_normalized TEXT      NOT NULL
                ,url_hash       TEXT      NOT NULL UNIQUE
            );
            CREATE INDEX IF NOT EXISTS idx_links_url_hash ON app_link.links (url_hash);
            CREATE INDEX IF NOT EXISTS idx_links_url_normalized ON app_link.links (url_normalized);
            """
        )
        logger.info("[LINK_MODEL] Таблица links создана/проверена")

    @classmethod
    async def get_existing_hashes(cls, hashes: List[str]) -> Set[str]:
        """Возвращает множество хешей, уже присутствующих в таблице."""
        if not hashes:
            return set()
        db = DBManager()
        query = "SELECT url_hash FROM app_link.links WHERE url_hash = ANY($1)"
        rows = await db.fetch_all(cls.DB_ALIAS, query, hashes)
        return {row["url_hash"] for row in rows}

    @classmethod
    async def insert_new_urls(cls, records: List[Tuple[str, str, str]]) -> List[str]:
        """Вставляет новые записи, возвращает хеши вставленных."""
        if not records:
            return []
        db = DBManager()
        query = """
            INSERT INTO app_link.links (url, url_normalized, url_hash)
            SELECT unnest($1::text[]), unnest($2::text[]), unnest($3::text[])
            ON CONFLICT (url_hash) DO NOTHING
            RETURNING url_hash
        """
        originals = [r[0] for r in records]
        normalized = [r[1] for r in records]
        hashes = [r[2] for r in records]
        rows = await db.fetch_all(cls.DB_ALIAS, query, originals, normalized, hashes)
        return [row["url_hash"] for row in rows]

    @classmethod
    async def send_to_kafka(cls, urls: List[str]) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for url in urls:
                await client.post(
                    f"{APP_KAFKA_URL}/produce",
                    json={"topic": KAFKA_TOPIC_LINKS, "value": {"url": url}}
                )
                logger.info(f"[KAFKA] Отправлена ссылка: {url}")

    # ----- Публичные методы для проверки -----

    @classmethod
    async def exists(cls, url: str) -> bool:
        """Проверяет, существует ли один URL в БД."""
        normalized = cls.normalize_url(url)
        hash_ = cls.hash_url(normalized)
        existing = await cls.get_existing_hashes([hash_])
        return bool(existing)

    @classmethod
    async def exists_many(cls, urls: List[str]) -> List[bool]:
        """Проверяет список URL на существование, возвращает список булевых значений."""
        if not urls:
            return []
        prepared = cls.prepare_urls(urls)
        hashes = [p[2] for p in prepared]
        existing = await cls.get_existing_hashes(hashes)
        return [h in existing for h in hashes]

    @classmethod
    async def process_links(cls, raw_urls: List[str]) -> LinkCheckResponse:
        """Основной метод: проверка, вставка, Kafka, формирование ответа."""
        prepared = cls.prepare_urls(raw_urls)
        hashes = [p[2] for p in prepared]

        existing_hashes = await cls.get_existing_hashes(hashes)
        new_hashes = [h for h in hashes if h not in existing_hashes]

        inserted_hashes = []
        if new_hashes:
            new_records = [p for p in prepared if p[2] in new_hashes]
            inserted_hashes = await cls.insert_new_urls(new_records)

        if inserted_hashes:
            inserted_urls = [p[0] for p in prepared if p[2] in inserted_hashes]
            await cls.send_to_kafka(inserted_urls)

        inserted_set = set(inserted_hashes)
        results = []
        for original, norm, h in prepared:
            status = "new" if h in inserted_set else "duplicate"
            results.append(
                LinkStatus(
                    url=original,
                    normalized=norm,
                    hash=h,
                    status=status,
                )
            )
        return LinkCheckResponse(results=results)
