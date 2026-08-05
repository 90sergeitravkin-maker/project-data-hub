# src/back/app_users/models.py
"""
SQLAlchemy модели для модуля app_users.
Все таблицы находятся в схеме app_users (не в public!).
Соответствует реальной SQL-схеме БД.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Boolean, DateTime, Integer, BigInteger, Text,
    ForeignKey, func
)
from sqlalchemy.dialects.postgresql import INET, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base

# === Схема БД для всех таблиц модуля ===
SCHEMA_NAME = "app_users"
TABLE_ARGS = {"schema": SCHEMA_NAME}


class AuthUser(Base):
    """
    Основной пользователь системы.
    Реальная таблица: app_users.auth_users (bigserial id).
    Используется в: register, login, get_profile, update_profile.
    """
    __tablename__ = "auth_users"
    __table_args__ = TABLE_ARGS

    # Переопределяем id из Base, т.к. в БД это bigserial (BigInteger)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Статусы аккаунта
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # updated_at обновляется триггером trg_update_users в БД
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Защита от брутфорса (поля есть в БД, но пока не используются в download.py)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    login_stats: Mapped[list["LoginStat"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["AuthRefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AuthUser(id={self.id}, username='{self.username}', email='{self.email}')>"


class LoginStat(Base):
    """
    История входов пользователей.
    Реальная таблица: app_users.login_stats.
    Используется в: UserService._log_login_attempt.
    """
    __tablename__ = "login_stats"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(f"{SCHEMA_NAME}.auth_users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    # В БД тип INET (поддержка IPv4 и IPv6)
    ip_address: Mapped[Optional[str]] = mapped_column(INET, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # В БД тип UUID (gen_random_uuid())
    session_id: Mapped[Optional[str]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )

    user: Mapped["AuthUser"] = relationship(back_populates="login_stats")

    def __repr__(self) -> str:
        return f"<LoginStat(user_id={self.user_id}, success={self.success}, at={self.login_at})>"


class AuthRefreshToken(Base):
    """
    Хранилище Refresh токенов.
    Реальная таблица: app_users.auth_refresh_tokens.

    ⚠️ КРИТИЧНО: Сейчас в download.py refresh_token генерируется,
    но НЕ сохраняется в БД. Без этой таблицы невозможно:
    - Делать Logout (отзывать токены)
    - Проверять валидность refresh_token
    - Отслеживать активные сессии
    """
    __tablename__ = "auth_refresh_tokens"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(f"{SCHEMA_NAME}.auth_users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["AuthUser"] = relationship(back_populates="refresh_tokens")

    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_expired(self) -> bool:
        return datetime.now(self.expires_at.tzinfo) > self.expires_at


# ============================================================================
# МОДЕЛИ-ЗАДЕЛ НА БУДУЩЕЕ (таблицы есть в БД, но пока не используются)
# Описаны для консистентности с init_db.py и полной картины схемы.
# ============================================================================

class AuthRole(Base):
    """Роли пользователей (RBAC). Пока не используется."""
    __tablename__ = "auth_roles"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AuthUserRole(Base):
    """Связь пользователей с ролями (многие-ко-многим)."""
    __tablename__ = "auth_user_roles"
    __table_args__ = TABLE_ARGS

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(f"{SCHEMA_NAME}.auth_users.id", ondelete="CASCADE"),
        primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{SCHEMA_NAME}.auth_roles.id", ondelete="CASCADE"),
        primary_key=True
    )


class AuthEmailToken(Base):
    """Токены для верификации email и сброса пароля."""
    __tablename__ = "auth_email_tokens"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(f"{SCHEMA_NAME}.auth_users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # 'verify', 'reset'
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuthRateLimit(Base):
    """Rate limiting для защиты от брутфорса."""
    __tablename__ = "auth_rate_limits"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )