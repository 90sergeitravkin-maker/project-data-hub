# src/front/web_lk/api.py
"""
Простой веб-интерфейс для личного кабинета.
Все веб-страницы помечены тегом "WEB LK" для фильтрации в /docs-web
"""
from pydantic import ValidationError
from fastapi import APIRouter, Request, Form, HTTPException, Depends, status, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse

from src.core.logger import logger
from src.core.security import decode_token
from src.front.web_lk.config import templates, TAG_NAME, API_PREFIX_V1
from src.back.app_users.api import extract_client_info
from src.back.app_users.services import UserService
from src.back.app_users.schemas import LoginRequest, RegisterRequest
from src.back.app_users.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_COOKIE_SECURE, JWT_COOKIE_HTTPONLY, JWT_COOKIE_SAMESITE
)
import jwt
from src.core.env_loader import get_secret

# Инициализация роутера с тегом по умолчанию
router = APIRouter(tags=[TAG_NAME])


def get_current_user_id_from_cookie(access_token: str | None = Cookie(None, alias="access_token")) -> int:
    logger.debug(f"[AUTH] Cookie 'access_token': {'есть' if access_token else 'НЕТ'}")
    if access_token:
        logger.debug(f"[AUTH] Token (первые 20 символов): {access_token[:20]}...")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация. Cookie 'access_token' не найдена."
        )
    try:
        secret_key = get_secret("JWT_SECRET_KEY", "change-me-in-production!").get_secret_value()
        # Декодируем токен без проверки алгоритма (для совместимости)
        payload = jwt.decode(access_token, secret_key, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Невалидный токен")
        return int(user_id)
    except jwt.InvalidTokenError as e:
        logger.error(f"[AUTH] Ошибка декодирования токена: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия истекла или невалидна. Войдите снова."
        )
    except Exception as e:
        logger.error(f"[AUTH] Неожиданная ошибка: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ошибка авторизации."
        )


@router.get("/login", response_class=HTMLResponse, tags=[TAG_NAME])
async def login_page(request: Request, error: str = None, success: str = None):
    return templates.TemplateResponse(
        name="web_lk/login.html",
        request=request,
        context={"error": error, "success": success, "form_data": {}, "csrf_token": ""}
    )


@router.post("/login", response_class=HTMLResponse, tags=[TAG_NAME])
async def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        login_data = LoginRequest(email=email, password=password)
        info = extract_client_info(request)
        result = await UserService.login(
            login_data,
            ip_address=info["ip_address"],
            user_agent=info["user_agent"]
        )
        redirect_response = RedirectResponse(url=f"{API_PREFIX_V1}/profile", status_code=303)
        redirect_response.set_cookie(
            key="access_token",
            value=result["access_token"],
            httponly=JWT_COOKIE_HTTPONLY,
            secure=JWT_COOKIE_SECURE,
            samesite=JWT_COOKIE_SAMESITE,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/"
        )
        return redirect_response
    except HTTPException as e:
        return RedirectResponse(url=f"{API_PREFIX_V1}/login?error={e.detail}", status_code=303)
    except Exception as e:
        logger.error(f"[WEB] Ошибка входа: {type(e).__name__}: {e}", exc_info=True)
        error_msg = "Неверный email или пароль"
        if "connection" in str(e).lower() or "pool" in str(e).lower():
            error_msg = "Сервис временно недоступен"
        return RedirectResponse(url=f"{API_PREFIX_V1}/login?error={error_msg}", status_code=303)


@router.get("/logout", tags=[TAG_NAME])
async def logout():
    """
    Выход из системы: удаляет access_token cookie и перенаправляет на страницу входа.
    """
    response = RedirectResponse(url=f"{API_PREFIX_V1}/login", status_code=303)
    response.delete_cookie("access_token", path="/")
    return response


@router.get("/register", response_class=HTMLResponse, tags=[TAG_NAME])
async def register_page(request: Request, error: str = None, success: str = None):
    return templates.TemplateResponse(
        name="web_lk/register.html",
        request=request,
        context={"error": error, "success": success, "form_data": {}, "csrf_token": ""}
    )


@router.post("/register", response_class=HTMLResponse, tags=[TAG_NAME])
async def register_submit(request: Request,
                          email: str = Form(...), username: str = Form(...),
                          password: str = Form(...), password_confirm: str = Form(...)):
    if password != password_confirm:
        return RedirectResponse(url=f"{API_PREFIX_V1}/register?error=Пароли+не+совпадают", status_code=303)
    try:
        await UserService.register(RegisterRequest(email=email, username=username, password=password))
        return RedirectResponse(
            url=f"{API_PREFIX_V1}/login?success=Регистрация+успешна.+Войдите+в+систему.",
            status_code=303
        )
    except ValidationError as e:
        error_msg = e.errors()[0]['msg'] if e.errors() else "Ошибка валидации"
        return RedirectResponse(url=f"{API_PREFIX_V1}/register?error={error_msg}", status_code=303)
    except HTTPException as e:
        return RedirectResponse(url=f"{API_PREFIX_V1}/register?error={e.detail}", status_code=303)
    except Exception as e:
        logger.error(f"[WEB] Ошибка регистрации: {e}", exc_info=True)
        return RedirectResponse(url=f"{API_PREFIX_V1}/register?error=Ошибка+сервера", status_code=303)


@router.get("/profile", response_class=HTMLResponse, summary="Страница профиля", tags=[TAG_NAME])
async def profile_page(request: Request, user_id: int = Depends(get_current_user_id_from_cookie)):
    try:
        user_data = await UserService.get_profile(user_id)
        stats = await UserService.get_login_summary(user_id)
        return templates.TemplateResponse(
            name="web_lk/profile.html",
            request=request,
            context={"user": user_data, "stats": stats, "csrf_token": ""}
        )
    except HTTPException as e:
        if e.status_code == 404:
            return templates.TemplateResponse(
                name="web_lk/login.html",
                request=request,
                context={"error": "Пользователь не найден. Возможно, аккаунт был удалён.", "success": None,
                         "form_data": {}, "csrf_token": ""}
            )
        raise
    except Exception as e:
        logger.error(f"[WEB_LK] Ошибка загрузки профиля: {e}", exc_info=True)
        return templates.TemplateResponse(
            name="web_lk/login.html",
            request=request,
            context={"error": "Ошибка загрузки данных. Попробуйте войти снова.", "success": None, "form_data": {},
                     "csrf_token": ""}
        )


@router.get("/test", response_class=HTMLResponse, tags=[TAG_NAME])
async def test_page(request: Request):
    return templates.TemplateResponse(
        name="web_lk/test.html",
        request=request
    )
