# src/back/app_datasets/schemas.py
import json
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")


class DataSetCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    period: Optional[str] = Field(None, max_length=255)
    date_updated: Optional[str] = Field(None, max_length=255)
    link: Optional[str] = Field(None, max_length=255)
    validation: Optional[dict[str, Any] | list[Any]] = Field(None)

    @field_validator('period', mode='before')
    @classmethod
    def convert_period_to_str(cls, value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return value.strip() if value.strip() else None
        return str(value)


class DataSetResponse(BaseSchema):
    id: int
    date_created: Optional[str] = None
    name: Optional[str] = None
    period: Optional[str] = None
    date_updated: Optional[str] = None
    link: Optional[str] = None
    validation: Optional[dict[str, Any] | list[Any]] = None

    @field_validator('date_created', mode='before')
    @classmethod
    def format_date_created(cls, value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            return value
        return str(value) if value else None

    @field_validator('validation', mode='before')
    @classmethod
    def parse_validation(cls, value):
        if value is None or isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value


class DataSetUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)

    period: Optional[str] = Field(None, max_length=255)
    date_updated: Optional[str] = Field(None, max_length=255)
    link: Optional[str] = Field(None, max_length=255)
    validation: Optional[dict[str, Any] | list[Any]] = Field(None)

    @field_validator('period', mode='before')
    @classmethod
    def convert_period_to_str(cls, value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return value.strip() if value.strip() else None
        return str(value)


class DataSetAggregateResponse(BaseSchema):
    """Ответ агрегации: сумма size/rows по name+period"""
    name: str
    period: Optional[str] = None
    size: Optional[int] = None  # сумма (validation->>'size')::int
    rows: Optional[int] = None  # сумма (validation->>'rows')::int
