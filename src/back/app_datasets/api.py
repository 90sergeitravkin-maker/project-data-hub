# src/back/app_datasets/api.py
from typing import AsyncGenerator, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.back.app_datasets.services import DataSetsVerifiedServices
from src.core.logger import logger
from src.database.session import get_async_session
from src.back.app_datasets.config import DB_ALIAS, TAG_NAME
from src.back.app_datasets.schemas import (
    DataSetAggregateResponse,
    DataSetCreate,
    DataSetResponse,
)

router = APIRouter(tags=[TAG_NAME])


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Сессия строго в пуле приложения (не base_01)."""
    async for session in get_async_session(alias=DB_ALIAS):
        yield session


@router.get(
    "/aggregate",
    response_model=list[DataSetAggregateResponse],
    summary="Агрегация данных по name и period",
)
async def aggregate_datasets(
        name: str = Query(..., min_length=1, description="Имя датасета для фильтрации"),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        session: AsyncSession = Depends(get_db_session),
) -> list[DataSetAggregateResponse]:
    return await DataSetsVerifiedServices.aggregate_by_name(session, name_filter=name, skip=skip, limit=limit)


@router.get("/", response_model=List[DataSetResponse], summary="Список всех датасетов")
async def list_datasets(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        session: AsyncSession = Depends(get_db_session),
) -> List[DataSetResponse]:
    return await DataSetsVerifiedServices.get_all(session, skip=skip, limit=limit)


@router.get("/{dataset_id}", response_model=DataSetResponse, summary="Получить датасет по ID")
async def get_dataset(dataset_id: int, session: AsyncSession = Depends(get_db_session)) -> DataSetResponse:
    return await DataSetsVerifiedServices.get_by_id(session, dataset_id)


@router.post(
    "/",
    response_model=DataSetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новую запись датасета",
)
async def create_dataset(data: DataSetCreate, session: AsyncSession = Depends(get_db_session)) -> DataSetResponse:
    return await DataSetsVerifiedServices.create(session, data)


@router.post("/scan-verified", summary="Сканировать папки")
async def scan_verified_datasets():
    await DataSetsVerifiedServices.scan_and_save()
    await DataSetsVerifiedServices.check_and_update_missing_files(batch_size=1000)
    return {"status": "ok", "message": "Сканирование и сохранение завершены"}


@router.post("/check-missing-files")
async def check_missing_files(batch_size: int = 1000):
    try:
        result = await DataSetsVerifiedServices.check_and_update_missing_files(batch_size=batch_size)
        return {
            "status": "ok",
            "message": "Проверка файлов завершена",
            "checked": result["checked"],
            "missing": result["missing"],
            "updated": result["updated"],
        }
    except Exception as e:
        logger.error(f"Ошибка при проверке файлов: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
