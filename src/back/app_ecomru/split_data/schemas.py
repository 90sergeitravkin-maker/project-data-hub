#  src/back/app_ecomru/split_data/schemas.py
from typing import Optional

from pydantic import BaseModel


class ProcessRequest(BaseModel):
    folder_path: str


class ProcessResponse(BaseModel):
    status: str
    message: Optional[str] = None
    data: Optional[dict] = None
