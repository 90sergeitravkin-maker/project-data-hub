# src/back/app_users/api.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.responses import RedirectResponse

from src.back.app_users.config import TAG_NAME, API_PREFIX_V1
from src.back.app_users.schemas import (
    RegisterRequest, LoginRequest, UserProfileResponse,
    TokenResponse, UpdateProfileRequest, LoginStatResponse,
    LoginStatsSummary, LoginStatsQuery
)
from src.back.app_users.services import UserService
from src.core.security import get_authx  # или decode_token

router = APIRouter(tags=[TAG_NAME])
security = HTTPBearer()

# Получаем экземпляр authx (или используем decode_token)
authx = get_authx()


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    try:
        payload = authx.decode_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(401, "Невалидный токен")
        return int(user_id)
    except Exception:
        raise HTTPException(401, "Ошибка авторизации")


def extract_client_info(request: Request) -> dict:
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    return {"ip_address": ip, "user_agent": ua}


@router.post("/register", summary="Регистрация нового пользователя", status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest) -> dict:
    return await UserService.register(request)


@router.post("/login", summary="Вход в личный кабинет", response_model=TokenResponse)
async def login(request: LoginRequest, req: Request) -> dict:
    info = extract_client_info(req)
    return await UserService.login(request, ip_address=info["ip_address"], user_agent=info["user_agent"])


@router.post("/logout", tags=[TAG_NAME])
async def logout():
    response = RedirectResponse(url=f"{API_PREFIX_V1}/login", status_code=303)
    response.delete_cookie("access_token", path="/")
    return response


@router.get("/profile", response_model=UserProfileResponse, summary="Мой профиль")
async def get_profile(user_id: int = Depends(get_current_user_id)) -> dict:
    return await UserService.get_profile(user_id)


@router.patch("/profile", response_model=UserProfileResponse, summary="Обновить профиль")
async def update_profile(data: UpdateProfileRequest, user_id: int = Depends(get_current_user_id)) -> dict:
    return await UserService.update_profile(user_id, username=data.username)


# === Статистика ===
@router.get("/login-stats", response_model=list[LoginStatResponse], summary="История входов")
async def get_login_history(query: LoginStatsQuery = Depends(), user_id: int = Depends(get_current_user_id)) -> list:
    return await UserService.get_login_stats(user_id, query)


@router.get("/login-stats/summary", response_model=LoginStatsSummary, summary="Сводка по входам")
async def get_login_summary(user_id: int = Depends(get_current_user_id)) -> dict:
    return await UserService.get_login_summary(user_id)
