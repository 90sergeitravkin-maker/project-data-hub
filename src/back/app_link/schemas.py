# src/back/app_link/schemas.py
from pydantic import BaseModel, HttpUrl
from typing import List, Optional


class LinkExistsRequest(BaseModel):
    url: HttpUrl


class LinksExistsRequest(BaseModel):
    urls: List[HttpUrl]


class LinkStatus(BaseModel):
    url: str
    normalized: str
    hash: str
    status: str  # "new" или "duplicate"


class LinkCheckResponse(BaseModel):
    results: List[LinkStatus]


class LinkExistsItem(BaseModel):
    url: str
    exists: bool
    normalized: Optional[str] = None
    hash: Optional[str] = None


class LinkExistsResponse(BaseModel):
    results: List[LinkExistsItem]
