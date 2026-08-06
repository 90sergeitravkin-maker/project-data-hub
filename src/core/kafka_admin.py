# src/core/kafka_admin.py
"""
Асинхронное администрирование Kafka через aiokafka.
Возвращает все топики и группы без фильтрации.
"""

import logging
from typing import List, Dict, Any, Optional

from aiokafka import AIOKafkaConsumer, TopicPartition
from aiokafka.admin import AIOKafkaAdminClient, NewTopic

from src.core.env_loader import get_env
from src.core.logger import logger

BOOTSTRAP = get_env("KAFKA_BOOTSTRAP", "localhost:9092")
REQUEST_TIMEOUT = int(get_env("KAFKA_REQUEST_TIMEOUT_MS", "10000"))


async def get_admin_client() -> AIOKafkaAdminClient:
    """Создаёт и возвращает административный клиент Kafka."""
    return AIOKafkaAdminClient(
        bootstrap_servers=BOOTSTRAP,
        request_timeout_ms=REQUEST_TIMEOUT,
    )


async def topic_exists(topic_name: str) -> bool:
    """Проверяет существование топика."""
    admin = await get_admin_client()
    try:
        await admin.start()
        topics = await admin.list_topics()
        return topic_name in topics
    except Exception as e:
        logger.error(f"[KAFKA_ADMIN] Ошибка проверки топика {topic_name}: {e}")
        return False
    finally:
        await admin.close()


async def ensure_topics(topics: List[str], partitions: int = 1, replication: int = 1) -> None:
    """
    Создаёт указанные топики, если они ещё не существуют.

    Args:
        topics: Список имён топиков.
        partitions: Количество партиций (по умолчанию 1).
        replication: Коэффициент репликации (по умолчанию 1).
    """
    admin = await get_admin_client()
    try:
        await admin.start()
        existing = await admin.list_topics()
        to_create = [
            NewTopic(name=t, num_partitions=partitions, replication_factor=replication)
            for t in topics if t not in existing
        ]
        if to_create:
            await admin.create_topics(to_create)
            logger.info(f"[KAFKA_ADMIN] Созданы топики: {[t.name for t in to_create]}")
    except Exception as e:
        logger.error(f"[KAFKA_ADMIN] Ошибка создания топиков: {e}")
    finally:
        await admin.close()


async def list_topics() -> List[Dict[str, Any]]:
    """
    Возвращает список всех неслужебных топиков с информацией о партициях.

    Использует внутренний кластерный метаданные, чтобы избежать ошибок
    при работе с разными версиями aiokafka.

    Returns:
        Список словарей с ключами: name, partitions, configs, description.
    """
    admin = await get_admin_client()
    try:
        await admin.start()
        cluster = admin._client.cluster
        all_topics = cluster.topics()  # множество всех топиков

        result = []
        for topic in all_topics:
            if topic.startswith("__"):          # пропускаем служебные
                continue

            partitions = []
            topic_partitions = cluster.partitions_for_topic(topic) or []
            for p in topic_partitions:
                tp = TopicPartition(topic, p)
                partitions.append({
                    "partition": p,
                    "leader": cluster.leader_for_partition(tp),
                    "replicas": list(cluster.replicas_for_partition(tp) or []),
                    "isr": list(cluster.isr_for_partition(tp) or []),
                })

            result.append({
                "name": topic,
                "partitions": partitions,
                "configs": {},
                "description": None,
            })

        result.sort(key=lambda t: t["name"])
        logger.info(f"[KAFKA_ADMIN] Получено {len(result)} топиков")
        return result
    except Exception as e:
        logger.error(f"[KAFKA_ADMIN] Ошибка list_topics: {e}", exc_info=True)
        raise
    finally:
        await admin.close()


async def list_groups() -> List[Dict[str, Any]]:
    """
    Возвращает список всех consumer groups с деталями.

    Поддерживает как строки, так и кортежи (group_id, protocol_type),
    возвращаемые разными версиями aiokafka.

    Returns:
        Список словарей с ключами: group_id, protocol_type, state, members.
    """
    admin = await get_admin_client()
    try:
        await admin.start()
        raw_groups = await admin.list_consumer_groups()
        logger.debug(f"[KAFKA_ADMIN] Сырые группы: {raw_groups}")

        result = []
        for group in raw_groups:
            # Извлекаем group_id из кортежа или строки
            if isinstance(group, tuple):
                group_id = group[0]
            else:
                group_id = group

            try:
                desc = await admin.describe_consumer_groups([group_id])
                group_desc = desc[group_id]
                members = [
                    {
                        "member_id": m.member_id,
                        "client_id": m.client_id,
                        "host": m.client_host,
                    }
                    for m in group_desc.members
                ]
                result.append({
                    "group_id": group_id,
                    "protocol_type": group_desc.protocol_type,
                    "state": group_desc.state,
                    "members": members,
                })
            except Exception as e:
                logger.warning(f"[KAFKA_ADMIN] Группа {group_id}: {e}")
                result.append({
                    "group_id": group_id,
                    "protocol_type": "unknown",
                    "state": "unknown",
                    "members": [],
                })

        result.sort(key=lambda g: g["group_id"])
        logger.info(f"[KAFKA_ADMIN] Получено {len(result)} групп")
        return result
    except Exception as e:
        logger.error(f"[KAFKA_ADMIN] Ошибка list_groups: {e}", exc_info=True)
        raise
    finally:
        await admin.close()


async def get_group_lags(group_id: str) -> List[Dict[str, Any]]:
    """
    Вычисляет lag (отставание) для каждой партиции указанной consumer group.

    Args:
        group_id: Идентификатор группы потребителей.

    Returns:
        Список словарей с информацией о lag для каждой партиции.
    """
    admin = await get_admin_client()
    consumer: Optional[AIOKafkaConsumer] = None
    try:
        await admin.start()
        cluster = admin._client.cluster

        all_tps: List[TopicPartition] = []
        for topic in cluster.topics():
            if topic.startswith("__"):
                continue
            for p in cluster.partitions_for_topic(topic) or []:
                all_tps.append(TopicPartition(topic, p))

        if not all_tps:
            return []

        consumer = AIOKafkaConsumer(
            bootstrap_servers=BOOTSTRAP,
            group_id=group_id,
            enable_auto_commit=False,
        )
        await consumer.start()

        committed = await consumer.committed(*all_tps)
        end_offsets = await consumer.end_offsets(all_tps)

        lags = []
        for tp in all_tps:
            committed_offset = committed.get(tp)
            if committed_offset is None:
                continue
            end = end_offsets.get(tp, 0)
            lags.append({
                "topic": tp.topic,
                "partition": tp.partition,
                "current_offset": committed_offset,
                "end_offset": end,
                "lag": max(0, end - committed_offset),
            })

        return lags
    except Exception as e:
        logger.error(f"[KAFKA_ADMIN] Ошибка get_group_lags({group_id}): {e}", exc_info=True)
        return []
    finally:
        if consumer:
            await consumer.stop()
        await admin.close()