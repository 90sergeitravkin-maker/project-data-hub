# src/back/app_data_registry/api.py
import httpx
import json
import asyncpg

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Query

from src.core.logger import logger
from src.database.manager import DBManager
from src.back.app_data_registry.config import (
    TAG_NAME, DB_ALIAS, CHECK_DATA_URL,
    CHECK_TIMEOUT, CHECK_SERVICE_TOKEN
)
from src.back.app_data_registry.schemas import (
    ServiceCreate,
    SourceCreate,
    ServiceResponse,
    SourceResponse,
    CheckResponse
)

router = APIRouter(tags=[TAG_NAME])
db_manager = DBManager()


# ================= CRUD: Services =================
@router.get("/download", response_model=List[ServiceResponse])
async def list_services(is_active: Optional[bool] = Query(None)):
    query = """
        SELECT id, name, description, is_active, created_at, updated_at 
        FROM app_data_registry.download 
        WHERE 1=1
    """
    params = []
    if is_active is not None:
        query += " AND is_active = $1"
        params.append(is_active)
    query += " ORDER BY name"
    rows = await db_manager.fetch_all(DB_ALIAS, query, *params)
    return rows


@router.post("/download", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(data: ServiceCreate):
    query = """
        INSERT INTO app_data_registry.download (name, description)
        VALUES ($1, $2)
        RETURNING id, name, description, is_active, created_at, updated_at
    """
    try:
        row = await db_manager.fetch_one(DB_ALIAS, query, data.name, data.description)
        return row
    except asyncpg.exceptions.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Сервис с именем '{data.name}' уже существует"
        )


# ================= CRUD: Sources =================
@router.get("/sources", response_model=List[SourceResponse])
async def list_sources(service_name: Optional[str] = Query(None, include_in_schema=False)):
    name = service_name.strip() if service_name else None

    query = """
        SELECT 
              ds.id          AS id
             ,ds.service_id  AS service_id
             ,s.name         AS service_name
             ,ds.name        AS name
             ,ds.source_type AS source_type
             ,ds.config      AS config
             ,ds.is_active   AS is_active
             ,ds.created_at  AS created_at
             ,ds.updated_at  AS updated_at
        FROM app_data_registry.data_sources ds
            JOIN app_data_registry.download s ON ds.service_id = s.id
    """
    params = []
    if name:
        query += " WHERE s.name = $1"
        params.append(name)
    query += " ORDER BY s.name, ds.name"

    rows = await db_manager.fetch_all(DB_ALIAS, query, *params)
    # Десериализация config, если пришла строка
    for row in rows:
        if isinstance(row.get("config"), str):
            try:
                row["config"] = json.loads(row["config"])
            except (json.JSONDecodeError, ValueError):
                pass
    return rows


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(data: SourceCreate):
    # 1. Находим service_id по имени
    svc = await db_manager.fetch_one(
        DB_ALIAS,
        "SELECT id FROM app_data_registry.download WHERE name = $1",
        data.service_name.strip()
    )
    if not svc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сервис '{data.service_name}' не найден"
        )
    service_id = svc["id"]

    # 2. Сериализация config в JSON
    config_json = json.dumps(data.config) if data.config else '{}'

    # 3. UPSERT
    query = """
        INSERT INTO app_data_registry.data_sources (service_id, name, source_type, config)
        VALUES ($1, $2, $3, $4::jsonb)
        ON CONFLICT (service_id, name) 
        DO UPDATE SET 
            source_type = EXCLUDED.source_type,
            config      = EXCLUDED.config,
            updated_at  = NOW()
        RETURNING 
            id, service_id, name, source_type, config::jsonb, is_active, created_at, updated_at
    """
    try:
        row = await db_manager.fetch_one(DB_ALIAS, query, service_id, data.name, data.source_type, config_json)
        if row:
            row["service_name"] = data.service_name
        return row
    except asyncpg.exceptions.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Источник '{data.name}' уже существует для сервиса '{data.service_name}'"
        )


# ================= CHECK ENDPOINT =================
@router.get("/check", response_model=CheckResponse, summary="Отправить источники сервиса в check-сервис")
async def check_sources(
        service_name: str = Query(..., min_length=2, max_length=100, description="Имя сервиса для проверки")
):
    service_name = service_name.strip().lower()

    # 1. Проверка существования сервиса
    svc = await db_manager.fetch_one(
        DB_ALIAS,
        """
        SELECT id, name 
        FROM app_data_registry.download 
        WHERE name = $1 AND is_active = TRUE
        """,
        service_name
    )
    if not svc:
        logger.warning(f"[REGISTRY] Сервис '{service_name}' не найден или неактивен")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сервис '{service_name}' не найден или деактивирован"
        )
    service_id = svc["id"]

    # 2. Запрос активных источников
    query = """
        SELECT 
             id, created_at, updated_at, is_active, service_id,
             name, source_type, config
        FROM app_data_registry.data_sources 
        WHERE service_id = $1 AND is_active = TRUE
        ORDER BY name
    """
    sources = await db_manager.fetch_all(DB_ALIAS, query, service_id)

    if not sources:
        logger.warning(f"[REGISTRY] Нет активных источников для сервиса '{service_name}'")
        return CheckResponse(
            status="completed",
            check_results={
                "service_name": service_name,
                "sources_count": 0,
                "message": "No active sources for this service"
            }
        )

    # 3. Нормализация данных для JSON
    def _normalize_value(val):
        if isinstance(val, datetime):
            return val.isoformat()
        if isinstance(val, dict):
            return {k: _normalize_value(v) for k, v in val.items()}
        if isinstance(val, (list, tuple)):
            return [_normalize_value(item) for item in val]
        return val

    normalized_sources = [_normalize_value(src) for src in sources]

    # 4. Формирование payload
    payload = {
        "folders": [i.get("name") for i in normalized_sources]
    }

    # 5. HTTP-вызов во внешний сервис
    try:
        async with httpx.AsyncClient(timeout=CHECK_TIMEOUT) as client:
            headers = {"Content-Type": "application/json"}
            if CHECK_SERVICE_TOKEN:
                headers["Authorization"] = f"Bearer {CHECK_SERVICE_TOKEN}"

            logger.info(
                f"[REGISTRY] Отправка {len(normalized_sources)} источников сервиса '{service_name}' в {CHECK_DATA_URL}")

            response = await client.post(CHECK_DATA_URL, json=payload, headers=headers)

            if response.status_code == 404:
                logger.error(f"[REGISTRY] Эндпоинт не найден: {CHECK_DATA_URL}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Эндпоинт проверки не существует: {CHECK_DATA_URL}"
                )

            response.raise_for_status()
            return CheckResponse(status="completed", check_results=response.json())

    except httpx.HTTPStatusError as e:
        logger.error(f"[REGISTRY] HTTP ошибка: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail={
                "error": "Check service error",
                "url": str(e.request.url),
                "method": e.request.method,
                "status": e.response.status_code,
                "response": e.response.text
            }
        )
    except httpx.RequestError as e:
        logger.error(f"[REGISTRY] Сетевая ошибка: {CHECK_DATA_URL} | {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Сервис проверки временно недоступен: {CHECK_DATA_URL}"
        )
    except Exception as e:
        logger.error(f"[REGISTRY] Неизвестная ошибка check: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal check error")
