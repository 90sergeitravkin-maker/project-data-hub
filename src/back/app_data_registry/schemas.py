#  src/back/app_data_registry/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class BaseSchema(BaseModel):
    model_config = {"from_attributes": True, "extra": "ignore"}


class ServiceCreate(BaseSchema):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None


class ServiceResponse(BaseSchema):
   # id: int
    name: str = Field(..., min_length=2, max_length=100)  # обязательное
    description: Optional[str] = None  # опциональное
    #is_active: bool
    #created_at: datetime
    #updated_at: datetime


class SourceCreate(BaseSchema):
    service_name: str = Field(..., min_length=2, max_length=100)  # ← ИЗМЕНЕНО
    name: str = Field(..., min_length=2, max_length=150)
    source_type: str = Field(..., min_length=2, max_length=50)
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SourceResponse(BaseSchema):
    # id: int
    # service_id: int
    service_name: Optional[str] = None  # ← ДОБАВЛЕНО
    name: str
    source_type: str
    config: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CheckPayload(BaseSchema):
    sources: List[SourceResponse]
    total: int


class CheckResponse(BaseSchema):
    status: str = "completed"
    check_results: Any  # Проксируем ответ от /api/v1/systems/check-data
