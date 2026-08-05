# src/back/app_mail/schemas.py
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID  # ← ДОБАВИТЬ ИМПОРТ


class BaseSchema(BaseModel):
    model_config = {"from_attributes": True, "extra": "ignore"}


class MailCreateRequest(BaseSchema):
    to: EmailStr
    subject: str = Field(..., min_length=1, max_length=255)
    text: str = Field(..., min_length=1, max_length=10000)


class TaskResponse(BaseSchema):
    task_id: str
    status: str = "queued"
    message: str = "Задача поставлена в очередь"


class TaskStatusResponse(BaseSchema):
    task_id: UUID
    status: str
