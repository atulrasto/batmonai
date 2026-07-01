from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.auth.jwt import create_access_token
from app.auth.password import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, Token
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _make_token(user: User) -> Token:
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "client_id": str(user.client_id) if user.client_id else None,
    }
    return Token(
        access_token=create_access_token(payload),
        must_change_password=user.must_change_password,
    )


@router.post("/login", response_model=Token)
async def login(
    data: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> Token:
    result = await session.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return _make_token(user)


@router.post("/change-password", response_model=Token)
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Token:
    """Works even when must_change_password=True — that is its purpose."""
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password incorrect")
    current_user.password_hash = hash_password(data.new_password)
    current_user.must_change_password = False
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return _make_token(current_user)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)
