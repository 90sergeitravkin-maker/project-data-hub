# src/front/web_datasets/api.py
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import get_async_session
from src.back.app_datasets.services import DataSetsVerified
from src.front.web_datasets.config import TAG_NAME, templates

router = APIRouter(tags=[TAG_NAME])


async def get_db_session() -> AsyncSession:
    async for session in get_async_session():
        yield session


@router.get("/aggregate", response_class=HTMLResponse)
async def aggregate_view(
        request: Request,
        name: str = Query(None),
        session: AsyncSession = Depends(get_db_session)
):
    results = []
    if name:
        results = await DataSetsVerified.aggregate_by_name(session, name_filter=name)

    return templates.TemplateResponse(
        request=request,
        name="web_datasets/aggregate.html",
        context={
            "request": request,
            "results": results,
            "name_filter": name or ""
        }
    )
