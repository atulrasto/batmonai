"""FastAPI dependencies for auth and tenant-scoped DB sessions."""
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.jwt import decode_token
from app.core.database import AsyncSessionLocal
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_401 = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Plain session — no RLS context. Used for auth lookups."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(token)
    if payload is None:
        raise _401
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise _401
    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise _401
    return user


async def require_password_changed(
    user: User = Depends(get_current_user),
) -> User:
    """Gate: all routes except /auth/change-password require this."""
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PASSWORD_CHANGE_REQUIRED",
        )
    return user


async def require_superuser(
    user: User = Depends(require_password_changed),
) -> User:
    if user.role != "superuser":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser only")
    return user


async def get_rls_session(
    user: User = Depends(require_password_changed),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Opens a DB session within an explicit transaction and sets the RLS context:
      - superuser  → SET LOCAL app.bypass_rls = 'true'   (sees all tenants)
      - client     → SET LOCAL app.current_client_id = '<uuid>'
    Transaction is committed on clean exit, rolled back on exception.
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            if user.role == "superuser":
                await session.execute(text("SET LOCAL app.bypass_rls = 'true'"))
                # RLS policy evaluates both sides of OR; setting a nil UUID avoids
                # the empty-string → UUID cast error when current_client_id is unset.
                await session.execute(
                    text("SET LOCAL app.current_client_id = '00000000-0000-0000-0000-000000000000'")
                )
            else:
                # SET LOCAL does not accept bind parameters in asyncpg;
                # user.client_id is a UUID (hex + hyphens only) so inline is safe.
                await session.execute(
                    text(f"SET LOCAL app.current_client_id = '{user.client_id}'")
                )
            yield session
