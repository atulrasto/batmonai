from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database (app user — non-superuser, subject to RLS)
    database_url: str
    database_url_sync: str

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # Superuser seed — plain str so .local / .internal domains work in dev
    superuser_email: str
    superuser_password: str

    # SMTP
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_tls: bool = True

    # Ingestion
    publish_interval_seconds: int = 10
    offline_multiplier: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
