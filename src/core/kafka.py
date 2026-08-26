# src/core/kafka.py
"""
Асинхронный Kafka-клиент: продюсер + консьюмеры.
Только aiokafka, без kafka-python.
"""
import asyncio
import json
import signal
from typing import Dict, Any, Callable, Optional, List

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError, KafkaError

from src.core.logger import logger
from src.core.env_loader import get_env


class InvalidMessageError(Exception):
    """Poison pill: сообщение коммитится и пропускается."""


class KafkaClient:
    """Singleton-клиент Kafka: продюсер + консьюмеры."""

    _instance: Optional["KafkaClient"] = None

    def __new__(cls) -> "KafkaClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self.bootstrap_servers = get_env("KAFKA_BOOTSTRAP", "localhost:9092")
        self.max_retries = int(get_env("KAFKA_MAX_RETRIES", "5"))
        self.retry_base_sec = int(get_env("KAFKA_RETRY_BASE_SEC", "30"))
        self.dlq_enabled = get_env("KAFKA_DLQ_ENABLED", "true").lower() in ("true", "1", "yes")

        self.producer: Optional[AIOKafkaProducer] = None
        self.consumers: Dict[str, AIOKafkaConsumer] = {}
        self.handlers: Dict[str, Callable] = {}
        self._consumer_configs: Dict[str, Dict] = {}
        self._running = False
        self._consumer_tasks: List[asyncio.Task] = []

    # ──────────────────────────────────────────────
    # Продюсер
    # ──────────────────────────────────────────────
    async def start(self) -> None:
        if self.producer is not None:
            return
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            enable_idempotence=True,
            acks="all",
        )
        await self.producer.start()
        logger.info(f"[KAFKA] Продюсер запущен, брокер: {self.bootstrap_servers}")

    async def send_message(
            self,
            topic: str,
            value: Dict[str, Any],
            key: Optional[str] = None,
    ) -> None:
        if not self.producer:
            raise RuntimeError("Продюсер не запущен. Вызовите start().")
        await self.producer.send(topic, value=value, key=key)
        logger.debug(f"[KAFKA] Отправлено в {topic}: key={key}")

    async def ping(self) -> bool:
        """Проверяет доступность брокера."""
        try:
            from src.core.kafka_admin import topic_exists
            # Любой запрос к брокеру
            from aiokafka.admin import AIOKafkaAdminClient
            admin = AIOKafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                request_timeout_ms=5000,
            )
            await admin.start()
            await admin.list_topics()
            await admin.close()
            return True
        except Exception:
            return False

    # ──────────────────────────────────────────────
    # Консьюмеры
    # ──────────────────────────────────────────────
    def register_consumer(
            self,
            topic: str,
            group_id: str,
            callback: Callable[[Dict], Any],
    ) -> None:
        self.handlers[topic] = callback
        self._consumer_configs[topic] = {"group_id": group_id}

    async def run_consumers(self) -> None:
        if not self.handlers:
            logger.warning("[KAFKA] Нет зарегистрированных обработчиков")
            return

        from src.core.kafka_admin import topic_exists

        self._running = True
        self._consumer_tasks = []

        for topic in self.handlers:
            exists = await topic_exists(topic)
            if not exists:
                logger.warning(f"[KAFKA] Топик {topic} не существует, консюмер не запущен")
                continue

            group_id = self._consumer_configs.get(topic, {}).get(
                "group_id", f"default-{topic}"
            )
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=group_id,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                auto_offset_reset="earliest",
                enable_auto_commit=False,
            )
            await consumer.start()
            self.consumers[topic] = consumer
            logger.info(f"[KAFKA] Консюмер для {topic} (group={group_id}) запущен")

            task = asyncio.create_task(
                self._consume_loop(consumer, self.handlers[topic]),
                name=f"consumer-{topic}",
            )
            self._consumer_tasks.append(task)

        if self._consumer_tasks:
            try:
                await asyncio.gather(*self._consumer_tasks)
            except asyncio.CancelledError:
                logger.info("[KAFKA] Консюмеры остановлены (CancelledError)")
        else:
            logger.warning("[KAFKA] Нет активных консюмеров")

    async def _consume_loop(
            self,
            consumer: AIOKafkaConsumer,
            callback: Callable,
    ) -> None:
        try:
            async for msg in consumer:
                if not self._running:
                    break
                await self._process_message(consumer, msg, callback)
        except asyncio.CancelledError:
            logger.info(f"[KAFKA] Консюмер остановлен (cancel)")
            raise
        except KafkaConnectionError as e:
            logger.error(f"[KAFKA] Потеря соединения с брокером: {e}")
        except Exception as e:
            logger.error(f"[KAFKA] Критическая ошибка консьюмера: {e}", exc_info=True)

    async def _process_message(
            self,
            consumer: AIOKafkaConsumer,
            msg,
            callback: Callable,
    ) -> None:
        attempt = 0
        while True:
            attempt += 1
            try:
                await callback(msg.value)
                await consumer.commit()
                break
            except InvalidMessageError as e:
                logger.warning(
                    f"[KAFKA] Poison pill, пропуск: "
                    f"topic={msg.topic} offset={msg.offset} | {e}"
                )
                await consumer.commit()
                break
            except asyncio.CancelledError:
                logger.warning(f"[KAFKA] Остановка без коммита: offset={msg.offset}")
                raise
            except Exception as e:
                if attempt > self.max_retries:
                    logger.error(
                        f"[KAFKA] Исчерпаны попытки ({self.max_retries}) "
                        f"для offset={msg.offset}: {e}"
                    )
                    await self._send_to_dlq(msg)
                    await consumer.commit()
                    break
                delay = min(self.retry_base_sec * attempt, 300)
                logger.error(
                    f"[KAFKA] Ошибка (попытка {attempt}): {e}; "
                    f"повтор через {delay}с"
                )
                await asyncio.sleep(delay)

    async def _send_to_dlq(self, msg) -> None:
        if not self.dlq_enabled or not self.producer:
            return
        try:
            await self.producer.send(
                f"{msg.topic}.dlq", value=msg.value, key=msg.key
            )
            logger.warning(f"[KAFKA] Сообщение отправлено в DLQ: {msg.topic}.dlq")
        except Exception as e:
            logger.error(f"[KAFKA] Не удалось отправить в DLQ: {e}")

    # ──────────────────────────────────────────────
    # Остановка
    # ──────────────────────────────────────────────
    async def stop(self) -> None:
        self._running = False

        # Останавливаем консьюмеров
        for task in self._consumer_tasks:
            task.cancel()
        if self._consumer_tasks:
            await asyncio.gather(*self._consumer_tasks, return_exceptions=True)
            self._consumer_tasks = []

        for consumer in self.consumers.values():
            await consumer.stop()
        self.consumers.clear()
        self.handlers.clear()

        # Останавливаем продюсер
        if self.producer:
            await self.producer.stop()
            self.producer = None

        logger.info("[KAFKA] Все клиенты остановлены")


kafka_client = KafkaClient()
