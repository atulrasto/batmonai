from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.core.config import get_settings

_settings = get_settings()


def create_access_token(data: dict[str, Any]) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(
        minutes=_settings.jwt_access_token_expire_minutes
    )
    payload["iat"] = datetime.now(timezone.utc)
    return jwt.encode(payload, _settings.jwt_secret_key, algorithm=_settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(
            token, _settings.jwt_secret_key, algorithms=[_settings.jwt_algorithm]
        )
    except JWTError:
        return None
