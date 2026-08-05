# src/back/app_users/download.py
"""
Бизнес-логика app_users.
Использует общие функции из core.security и core.db.
"""

import uuid
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from src.database.manager import DBManager
from core.logger import logger
from src.back.app_users.config import config
from src.back.app_users.schemas import (
    RegisterRequest, LoginRequest, LoginStatsQuery
)
from src.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
)

# Для удобства используем алиас БД из конфига
DB_ALIAS = config.db_alias


class UserService:
    @classmethod
    async def _log_login_attempt(
            cls,
            user_id: Optional[int],
            success: bool,
            ip_address: Optional[str] = None,
            user_agent: Optional[str] = None,
            failure_reason: Optional[str] = None,
            alias: str = DB_ALIAS,
    ) -> None:
        db = DBManager()
        await db.execute(
            alias,
            """
            INSERT INTO app_users.login_stats 
                   (user_id, ip_address, user_agent, success, failure_reason, session_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            user_id,
            ip_address,
            user_agent,
            success,
            failure_reason,
            str(uuid.uuid4()),
        )

    @classmethod
    async def register(
            cls,
            request: RegisterRequest,
            alias: str = DB_ALIAS,
    ) -> Dict[str, Any]:
        db = DBManager()

        # Проверка уникальности email
        exists = await db.fetch_one(alias, """
        SELECT 
            id 
        FROM app_users.auth_users 
        WHERE email = $1
        """, request.email)
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email уже зарегистрирован",
            )

        # Хеширование пароля (используем общую функцию)
        password_hash = hash_password(request.password)

        await db.execute(
            alias,
            """
            INSERT INTO app_users.auth_users 
                (email, username, password_hash, is_active)
            VALUES ($1, $2, $3, true)
            """,
            request.email,
            request.username,
            password_hash,
        )
        logger.info(f"Зарегистрирован пользователь: {request.email}")
        return {"message": "Успешная регистрация"}

    @classmethod
    async def login(
            cls,
            request: LoginRequest,
            ip_address: Optional[str] = None,
            user_agent: Optional[str] = None,
            alias: str = DB_ALIAS,
    ) -> Dict[str, Any]:
        db = DBManager()
        record = await db.fetch_one(
            alias,
            """
            SELECT 
                id, password_hash, is_active 
            FROM app_users.auth_users 
            WHERE email = $1""",
            request.email,
        )

        user_id = record["id"] if record else None

        # Проверка пароля (используем общую функцию)
        if not record or not verify_password(request.password, record["password_hash"]):
            await cls._log_login_attempt(
                user_id=user_id,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="invalid_credentials",
                alias=alias,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
            )

        if not record["is_active"]:
            await cls._log_login_attempt(
                user_id=user_id,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="account_disabled",
                alias=alias,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Аккаунт деактивирован",
            )

        # Успешный вход
        await cls._log_login_attempt(
            user_id=user_id,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent,
            alias=alias,
        )

        # Создание токенов (общие функции)
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    @classmethod
    async def get_profile(
            cls,
            user_id: int,
            alias: str = DB_ALIAS,
    ) -> Dict[str, Any]:
        db = DBManager()
        record = await db.fetch_one(
            alias,
            """
            SELECT 
                id, email, username, is_active, created_at
            FROM app_users.auth_users
            WHERE id = $1
            """,
            user_id,
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден",
            )
        return record

    @classmethod
    async def update_profile(
            cls,
            user_id: int,
            username: Optional[str] = None,
            alias: str = DB_ALIAS,
    ) -> Dict[str, Any]:
        if not username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нет данных для обновления",
            )
        db = DBManager()
        await db.execute(
            alias,
            """
            UPDATE app_users.auth_users 
                SET username = $1, updated_at = NOW() 
            WHERE id = $2
            """,
            username,
            user_id,
        )
        logger.info(f"Профиль пользователя {user_id} обновлён")
        return await cls.get_profile(user_id, alias=alias)

    # === Статистика ===
    @classmethod
    async def get_login_stats(
            cls,
            user_id: int,
            query: LoginStatsQuery,
            alias: str = DB_ALIAS,
    ) -> List[Dict[str, Any]]:
        db = DBManager()
        where = ["user_id = $1"]
        params = [user_id]
        idx = 2

        if query.success_filter is not None:
            where.append(f"success = ${idx}")
            params.append(query.success_filter)
            idx += 1

        sql = f"""
            SELECT
                id, user_id, login_at, ip_address, user_agent, success, failure_reason
            FROM app_users.login_stats
            WHERE {' AND '.join(where)}
            ORDER BY login_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.extend([query.limit, query.offset])
        return await db.fetch_all(alias, sql, *params)

    @classmethod
    async def get_login_summary(
            cls,
            user_id: int,
            alias: str = DB_ALIAS,
    ) -> Dict[str, Any]:
        db = DBManager()
        sql = """
            SELECT 
                COUNT(*) as total_attempts,
                COUNT(*) FILTER (WHERE success = true) as successful,
                COUNT(*) FILTER (WHERE success = false) as failed,
                MAX(login_at) as last_login_at,
                MAX(login_at) FILTER (WHERE success = true) as last_success_at
            FROM app_users.login_stats
            WHERE user_id = $1
        """
        record = await db.fetch_one(alias, sql, user_id)
        return record or {
            "total_attempts": 0,
            "successful": 0,
            "failed": 0,
            "last_login_at": None,
            "last_success_at": None,
        }
