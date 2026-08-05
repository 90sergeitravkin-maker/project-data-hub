# src/back/app_kafka/api.py
from typing import List
from fastapi import APIRouter, HTTPException, status

from src.back.app_kafka.config import TAG_NAME
from src.back.app_kafka.schemas import (
    TopicInfo, GroupInfo, GroupDetailResponse,
    ProduceRequest, ProduceResponse,
)
from src.back.app_kafka.services import kafka_service
from src.core.logger import logger

router = APIRouter(tags=[TAG_NAME])


@router.get("/health", summary="Проверка подключения к Kafka")
async def kafka_health():
    result = await kafka_service.async_check_connection()
    if not result.get("available"):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=result)
    return result


@router.get("/topics", response_model=List[TopicInfo], summary="Список всех топиков")
async def list_topics():
    try:
        return await kafka_service.async_list_topics()
    except Exception as e:
        logger.error(f"Ошибка получения топиков: {e}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/groups", response_model=List[GroupInfo], summary="Consumer groups")
async def list_groups():
    try:
        return await kafka_service.async_list_groups()
    except Exception as e:
        logger.error(f"Ошибка получения групп: {e}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/groups/{group_id}", response_model=GroupDetailResponse,
            summary="Детали группы + lag")
async def get_group_details(group_id: str):
    try:
        groups = await kafka_service.async_list_groups()
        group_info = next((g for g in groups if g.group_id == group_id), None)
        if not group_info:
            raise HTTPException(status.HTTP_404_NOT_FOUND,
                                detail=f"Группа {group_id} не найдена")
        lags = await kafka_service.async_get_group_lags(group_id)
        return GroupDetailResponse(
            group_id=group_info.group_id,
            state=group_info.state,
            protocol_type=group_info.protocol_type,
            members=group_info.members,
            lags=lags,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка деталей группы '{group_id}': {e}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/produce", response_model=ProduceResponse,
             status_code=status.HTTP_201_CREATED, summary="Отправить сообщение")
async def produce_message(request: ProduceRequest):
    try:
        return await kafka_service.produce_message(
            topic=request.topic, value=request.value,
            key=request.key, partition=request.partition,
        )
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))