# src/core/app_config.py
from typing import Optional, List, Dict
from pydantic import BaseModel, SecretStr

from src.core.secrets import SecureDSN
from src.core.env_loader import get_env, get_secret
from src.core.db_config import get_dsn, get_search_path


class AppConfig(BaseModel):
    app_name: str
    tag_name: str
    api_prefix: str
    version: str = "1.0.0"
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    db_alias: Optional[str] = None
    jwt_secret: SecretStr = SecretStr("change-me-in-production!")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    extra_secrets: Dict[str, SecretStr] = {}
    openapi_tags: Optional[List[Dict[str, str]]] = None   # <-- ДОБАВЛЕНО

    @classmethod
    def from_app_name(
            cls,
            app_name: str,
            tag_name: Optional[str] = None,
            db_alias: Optional[str] = None,
            **overrides
    ) -> "AppConfig":
        tag_name = tag_name or app_name.replace("_", " ").title()
        prefix = f"/api/v1/{app_name}"
        log_level = get_env(f"{app_name.upper()}_LOG_LEVEL", "INFO").upper()
        host = get_env(f"{app_name.upper()}_HOST", "127.0.0.1")
        port = int(get_env(f"{app_name.upper()}_PORT", "8000"))
        reload = get_env(f"{app_name.upper()}_RELOAD", "false").lower() in ("true", "1", "yes")
        jwt_secret = get_secret("JWT_SECRET_KEY", "change-me-in-production!")
        jwt_algorithm = get_env("JWT_ALGORITHM", "HS256")
        access_expire = int(get_env("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        refresh_expire = int(get_env("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

        if db_alias:
            try:
                get_dsn(db_alias)
            except Exception:
                pass

        return cls(
            app_name=app_name,
            tag_name=tag_name,
            api_prefix=prefix,
            log_level=log_level,
            host=host,
            port=port,
            reload=reload,
            db_alias=db_alias,
            jwt_secret=jwt_secret,
            jwt_algorithm=jwt_algorithm,
            access_token_expire_minutes=access_expire,
            refresh_token_expire_days=refresh_expire,
            **overrides
        )

    def get_db_dsn(self) -> Optional[SecureDSN]:
        if self.db_alias:
            return get_dsn(self.db_alias)
        return None

    def get_search_path(self) -> str:
        if self.db_alias:
            return get_search_path(self.db_alias)
        return "public"

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            SecretStr: lambda v: "********" if v else ""
        }