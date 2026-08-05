# src/back/app_link/api.py
from fastapi import APIRouter

from src.back.app_link.config import TAG_NAME
from src.back.app_link.services import Link
from src.back.app_link.schemas import (
    LinkCheckResponse,
    LinkExistsItem,
    LinkExistsResponse, LinkExistsRequest,
    LinksExistsRequest,
)

router = APIRouter(tags=[TAG_NAME])


@router.post("/exists", response_model=LinkExistsItem)
async def check_single_link(request: LinkExistsRequest) -> LinkExistsItem:
    """
    Проверяет один URL на существование в таблице.
    """
    raw = str(request.url)
    exists = await Link.exists(raw)
    return LinkExistsItem(url=raw, exists=exists)


@router.post("/exists_many", response_model=LinkExistsResponse)
async def check_many_links(request: LinksExistsRequest) -> LinkExistsResponse:
    """
    Проверяет несколько URL на существование.
    """
    raw_urls = [str(u) for u in request.urls]
    exists_list = await Link.exists_many(raw_urls)
    items = [LinkExistsItem(url=u, exists=e) for u, e in zip(raw_urls, exists_list)]
    return LinkExistsResponse(results=items)


@router.post("/process", response_model=LinkCheckResponse)
async def process_links(request: LinksExistsRequest) -> LinkCheckResponse:
    """
    Полный цикл: проверка, вставка новых, отправка в Kafka, ответ со статусами.
    """
    raw_urls = [str(u) for u in request.urls]
    return await Link.process_links(raw_urls)
