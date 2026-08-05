#  src/back/app_data_registry/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class BaseSchema(BaseModel):
    """Базовая схема с настройками Pydantic v2."""
    model_config = {"from_attributes": True, "extra": "ignore"}


# ================= CRUD: Services =================
class ServiceCreate(BaseSchema):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None


class ServiceResponse(BaseSchema):
    name: str
    description: Optional[str] = None


# ================= CRUD: Sources (AsyncPG API) =================
class SourceCreate(BaseSchema):
    """Используется в API на asyncpg (app_data_registry/api.py)."""
    service_name: str = Field(..., min_length=2, max_length=100)
    name: str = Field(..., min_length=2, max_length=150)
    source_type: str = Field(..., min_length=2, max_length=50)
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SourceResponse(BaseSchema):
    service_name: Optional[str] = None
    name: str
    source_type: str
    config: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ================= CRUD: Sources (SQLAlchemy Service) =================
class DataSourceCreate(BaseSchema):
    """Используется в DataRegistryService.create_source (SQLAlchemy ORM)."""
    name: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = None


# ================= Versioning =================
class ServiceVersionCreate(BaseSchema):
    """Используется в DataRegistryService.create_version."""
    version_number: int = Field(..., ge=1, description="Номер версии")
    is_active: bool = Field(True, description="Статус активности версии")
    data_source_names: List[str] = Field(
        default_factory=list, 
        description="Список имён источников для привязки к версии"
    )


class VersionExpandRequest(BaseSchema):
    """Используется в DataRegistryService.expand_version."""
    data_source_names_to_add: List[str] = Field(
        default_factory=list,
        description="Источники, которые необходимо добавить в существующую версию"
    )


# ================= Check Integration =================
class CheckPayload(BaseSchema):
    sources: List[SourceResponse]
    total: int


class CheckResponse(BaseSchema):
    status: str = "completed"
    check_results: Any  # Проксируем ответ от /api/v1/systems/check-data