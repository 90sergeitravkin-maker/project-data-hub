# src/back/app_kafka/services.py
from typing import List, Dict, Any, Optional

from fastapi import HTTPException, status

from src.core.logger import logger
from src.core.kafka import kafka_client
from src.core import kafka_admin
from src.back.app_kafka.schemas import ProduceResponse


class KafkaService:
    @staticmethod
    async def async_check_connection() -> Dict[str, Any]:
        """Асинхронная проверка подключения к брокеру."""
        available = await kafka_client.ping()
        if not available:
            return {
                "available": False,
                "bootstrap": kafka_client.bootstrap_servers,
                "error": "Брокер недоступен",
            }
        topics = await kafka_admin.list_topics()
        return {
            "available": True,
            "bootstrap": kafka_client.bootstrap_servers,
            "topics_count": len(topics),
        }

    @staticmethod
    async def produce_message(
            topic: str,
            value: Any,
            key: Optional[str] = None,
            partition: Optional[int] = None,
    ) -> ProduceResponse:
        if not kafka_client.producer:
            await kafka_client.start()

        future = await kafka_client.producer.send(
            topic, value=value, key=key, partition=partition
        )
        meta = await future
        return ProduceResponse(
            status="ok",
            topic=meta.topic,
            partition=meta.partition,
            offset=meta.offset,
            message="Сообщение отправлено",
        )

    @staticmethod
    async def async_list_topics() -> List[Dict[str, Any]]:
        return await kafka_admin.list_topics()

    @staticmethod
    async def async_list_groups() -> List[Dict[str, Any]]:
        return await kafka_admin.list_groups()

    @staticmethod
    async def async_get_group_lags(group_id: str) -> List[Dict[str, Any]]:
        return await kafka_admin.get_group_lags(group_id)


kafka_service = KafkaService()
