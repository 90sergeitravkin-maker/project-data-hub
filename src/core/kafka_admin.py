# src/core/kafka_admin.py
"""
Асинхронное администрирование Kafka через aiokafka.
Заменяет синхронный kafka-python полностью.
"""
from typing import List, Dict, Any, Optional

from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka import AIOKafkaConsumer, TopicPartition
from aiokafka.structs import OffsetAndMetadata

from src.core.env_loader import get_env
from src.core.logger import logger

BOOTSTRAP = get_env("KAFKA_BOOTSTRAP", "localhost:9092")
REQUEST_TIMEOUT = int(get_env("KAFKA_REQUEST_TIMEOUT_MS", "10000"))


async def get_admin_client() -> AIOKafkaAdminClient:
    """Создаёт асинхронный админ-клиент."""
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
    """Создаёт топики, если их нет."""
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
    """Список всех топиков с партициями."""
    admin = await get_admin_client()
    try:
        await admin.start()
        cluster = admin._client.cluster

        result = []
        for topic in cluster.topics():
            if topic.startswith("__"):
                continue
            partitions = []
            for p in cluster.partitions_for_topic(topic) or []:
                partitions.append({
                    "partition": p,
                    "leader": cluster.leader_for_partition(TopicPartition(topic, p)),
                    "replicas": list(cluster.replicas_for_partition(TopicPartition(topic, p)) or []),
                    "isr": list(cluster.isr_for_partition(TopicPartition(topic, p)) or []),
                })
            result.append({
                "name": topic,
                "partitions": partitions,
                "configs": {},
                "description": None,
            })

        result.sort(key=lambda t: t["name"])
        return result
    except Exception as e:
        logger.error(f"[KAFKA_ADMIN] Ошибка list_topics: {e}")
        return []
    finally:
        await admin.close()


async def list_groups() -> List[Dict[str, Any]]:
    """Список consumer groups."""
    admin = await get_admin_client()
    try:
        await admin.start()
        groups = await admin.list_consumer_groups()

        result = []
        for group_id in groups:
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
        return result
    except Exception as e:
        logger.error(f"[KAFKA_ADMIN] Ошибка list_groups: {e}")
        return []
    finally:
        await admin.close()


async def get_group_lags(group_id: str) -> List[Dict[str, Any]]:
    """Вычисляет lag для каждой партиции consumer group."""
    admin = await get_admin_client()
    consumer: Optional[AIOKafkaConsumer] = None
    try:
        await admin.start()
        cluster = admin._client.cluster

        # Собираем все партиции
        all_tps: List[TopicPartition] = []
        for topic in cluster.topics():
            if topic.startswith("__"):
                continue
            for p in cluster.partitions_for_topic(topic) or []:
                all_tps.append(TopicPartition(topic, p))

        if not all_tps:
            return []

        # Получаем committed offsets через consumer
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
        logger.error(f"[KAFKA_ADMIN] Ошибка get_group_lags({group_id}): {e}")
        return []
    finally:
        if consumer:
            await consumer.stop()
        await admin.close()
