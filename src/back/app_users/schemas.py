# src/back/app_users/schemas.py
"""
Pydantic схемы для app_users.
Наследуются от базовой схемы core.
"""

from datetime import datetime
from typing import Optional
from pydantic import EmailStr, Field
from src.core.schemas import BaseSchema


class RegisterRequest(BaseSchema):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str


class TokenResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserProfileResponse(BaseSchema):
    id: int
    email: str
    username: str
    is_active: bool
    created_at: datetime


class UpdateProfileRequest(BaseSchema):
    username: Optional[str] = Field(None, min_length=3, max_length=50)


# === Статистика входов ===
class LoginStatResponse(BaseSchema):
    id: int
    user_id: int
    login_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool
    failure_reason: Optional[str] = None


class LoginStatsSummary(BaseSchema):
    total_attempts: int
    successful: int
    failed: int
    last_login_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None


class LoginStatsQuery(BaseSchema):
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    success_filter: Optional[bool] = None
