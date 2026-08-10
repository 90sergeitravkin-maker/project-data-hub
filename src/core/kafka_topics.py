# src/core/kafka_topics.py
"""
Централизованный реестр всех Kafka-топиков приложения.
Собирает топики из конфигов приложений, поддерживает переопределение через .env.
"""
from typing import List, Dict, Any
from src.core.env_loader import get_env
from src.core.logger import logger


def get_required_topics() -> List[str]:
    topics = [
        get_env("APP_ECOMRU_KAFKA_TOPIC_DOWNLOAD", "ecomru-download"),
        get_env("APP_ECOMRU_KAFKA_TOPIC_VERIFICATION", "ecomru-verification"),
        get_env("APP_ECOMRU_KAFKA_TOPIC_TRANSFER", "ecomru-transfer"),
        get_env("APP_ECOMRU_KAFKA_TOPIC_PROCESS_FOLDER", "ecomru-process-folder"),
        get_env("APP_ECOMRU_KAFKA_TOPIC_PROCESS_FOLDER_RESULT", "ecomru-process-folder-result"),
        get_env("APP_LINK_KAFKA_TOPIC", "ecomru-links-topic"),
        # === НОВОЕ ===
        get_env("APP_ECOMRU_KAFKA_TOPIC_REPORT", "ecomru-report"),
    ]
    seen = set()
    unique = []
    for i_topic in topics:
        if i_topic not in seen:
            seen.add(i_topic)
            unique.append(i_topic)
    logger.info(f"[KAFKA_TOPICS] Требуемые топики ({len(unique)}): {unique}")
    return unique


def get_dlq_topics() -> List[str]:
    """Возвращает DLQ-топики для каждого основного топика."""
    return [f"{t}.dlq" for t in get_required_topics()]


def get_all_topics_with_dlq() -> List[str]:
    """Все топики: основные + DLQ."""
    return get_required_topics() + get_dlq_topics()


def get_topics_info() -> List[Dict[str, Any]]:
    """
    Подробная информация о топиках для API / мониторинга.
    """
    return [
        {
            "name": get_env("APP_ECOMRU_KAFKA_TOPIC_DOWNLOAD", "ecomru-download"),
            "group_id": get_env("APP_ECOMRU_KAFKA_GROUP_ID_DOWNLOAD", "ecomru-download-group"),
            "role": "consumer",
            "app": "app_ecomru",
            "description": "Задачи на скачивание файлов",
        },
        {
            "name": get_env("APP_ECOMRU_KAFKA_TOPIC_VERIFICATION", "ecomru-verification"),
            "group_id": get_env("APP_ECOMRU_KAFKA_GROUP_ID_VERIFICATION", "ecomru-verification-group"),
            "role": "consumer",
            "app": "app_ecomru",
            "description": "Задачи на верификацию и разбиение файлов",
        },
        {
            "name": get_env("APP_ECOMRU_KAFKA_TOPIC_TRANSFER", "ecomru-transfer"),
            "group_id": None,
            "role": "producer",
            "app": "app_ecomru",
            "description": "Передача результатов верификации на следующий этап",
        },
        {
            "name": get_env("APP_ECOMRU_KAFKA_TOPIC_PROCESS_FOLDER", "ecomru-process-folder"),
            "group_id": get_env("APP_ECOMRU_KAFKA_GROUP_ID_PROCESS_FOLDER", "ecomru-process-folder-group"),
            "role": "consumer",
            "app": "app_ecomru.check_data",
            "description": "Задачи на обработку папок (разбиение по столбцу)",
        },
        {
            "name": get_env("APP_ECOMRU_KAFKA_TOPIC_PROCESS_FOLDER_RESULT", "ecomru-process-folder-result"),
            "group_id": None,
            "role": "producer",
            "app": "app_ecomru.check_data",
            "description": "Результаты обработки папок",
        },
        {
            "name": get_env("APP_LINK_KAFKA_TOPIC", "ecomru-links-topic"),
            "group_id": None,
            "role": "producer",
            "app": "app_link",
            "description": "Новые ссылки для обработки",
        },
        {
            "name": get_env("APP_ECOMRU_KAFKA_TOPIC_REPORT", "ecomru-report"),
            "group_id": get_env("APP_ECOMRU_KAFKA_GROUP_ID_REPORT", "ecomru-report-group"),
            "role": "producer",
            "app": "app_ecomru",
            "description": "Итоговый отчёт pipeline для Airflow",
        },
    ]
