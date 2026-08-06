# src/core/kafka_admin.py
"""
Асинхронное администрирование Kafka через aiokafka.
Возвращает все топики и группы без фильтрации.
"""
from typing import List, Dict, Any, Optional
from aiokafka import AIOKafkaConsumer, TopicPartition
from aiokafka.admin import AIOKafkaAdminClient, NewTopic

from src.core.env_loader import get_env
from src.core.logger import logger

BOOTSTRAP = get_env("KAFKA_BOOTSTRAP", "localhost:9092")
REQUEST_TIMEOUT = int(get_env("KAFKA_REQUEST_TIMEOUT_MS", "10000"))


async def get_admin_client() -> AIOKafkaAdminClient:
    return AIOKafkaAdminClient(
        bootstrap_servers=BOOTSTRAP,
        request_timeout_ms=REQUEST_TIMEOUT,
    )


async def topic_exists(topic_name: str) -> bool:
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
    Возвращает список всех топиков (кроме служебных) с партициями.
    Использует describe_topics для получения деталей.
    """
    admin = await get_admin_client()
    try:
        await admin.start()
        # Получаем все имена топиков
        all_topics = await admin.list_topics()
        logger.debug(f"[KAFKA_ADMIN] Все топики: {all_topics}")

        # Получаем детали по каждому топику (кроме служебных)
        topics_to_describe = [t for t in all_topics if not t.startswith("__")]
        descriptions = await admin.describe_topics(topics=topics_to_describe)

        result = []
        for desc in descriptions:
            partitions = [
                {
                    "partition": p.partition,
                    "leader": p.leader,
                    "replicas": p.replicas,
                    "isr": p.isr,
                }
                for p in desc.partitions
            ]
            result.append({
                "name": desc.topic,
                "partitions": partitions,
                "configs": {},  # можно добавить через describe_configs, но для простоты оставим пустым
                "description": None,
            })

        result.sort(key=lambda t: t["name"])
        logger.info(f"[KAFKA_ADMIN] Получено {len(result)} топиков")
        return result
    except Exception as e:
        logger.error(f"[KAFKA_ADMIN] Ошибка list_topics: {e}", exc_info=True)
        # Пробрасываем исключение, чтобы клиент видел ошибку
        raise
    finally:
        await admin.close()


async def list_groups() -> List[Dict[str, Any]]:
    """
    Возвращает список всех consumer groups с деталями.
    Обрабатывает как строки, так и кортежи (group_id, protocol_type).
    """
    admin = await get_admin_client()
    try:
        await admin.start()
        raw_groups = await admin.list_consumer_groups()
        logger.debug(f"[KAFKA_ADMIN] Сырые группы: {raw_groups}")

        result = []
        for group in raw_groups:
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
