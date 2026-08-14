# src/back/app_ecomru/split_data/config.py
import os
from src.core.env_loader import get_env

# === Kafka топики для обработки папок ===
PROCESS_FOLDER_TOPIC        = get_env("APP_ECOMRU_KAFKA_TOPIC_PROCESS_FOLDER", "ecomru-process-folder")
PROCESS_FOLDER_GROUP_ID     = get_env("APP_ECOMRU_KAFKA_GROUP_ID_PROCESS_FOLDER", "ecomru-process-folder-group")
PROCESS_FOLDER_RESULT_TOPIC = get_env("APP_ECOMRU_KAFKA_TOPIC_PROCESS_FOLDER_RESULT", "ecomru-process-folder-result")