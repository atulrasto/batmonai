import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_rls_session, require_password_changed
from app.auth.password import hash_password
from app.core.uid import unique_appliance_uid
from app.models.appliance import Appliance
from app.models.site import Site
from app.models.user import User
from app.schemas.appliance import ApplianceCreate, ApplianceOut, ApplianceUpdate

router = APIRouter(prefix="/appliances", tags=["appliances"])


def _resolve_client_id(data_client_id: uuid.UUID | None, user: User) -> uuid.UUID:
    if user.role == "superuser":
        if data_client_id is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="client_id required for superuser")
        return data_client_id
    return user.client_id  # type: ignore[return-value]


@router.post("/", response_model=ApplianceOut, status_code=status.HTTP_201_CREATED)
async def create_appliance(
    data: ApplianceCreate,
    user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> ApplianceOut:
    client_id = _resolve_client_id(data.client_id, user)
    site_result = await session.execute(select(Site).where(Site.id == data.site_id))
    site = site_result.scalar_one_or_none()
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    appliance_uid = await unique_appliance_uid(session, site.slug)
    appliance = Appliance(
        client_id=client_id,
        site_id=data.site_id,
        appliance_uid=appliance_uid,
        name=data.name,
        device_secret_hash=hash_password(data.device_secret),
    )
    session.add(appliance)
    await session.flush()
    await session.refresh(appliance)
    return ApplianceOut.model_validate(appliance)


@router.get("/", response_model=list[ApplianceOut])
async def list_appliances(
    session: AsyncSession = Depends(get_rls_session),
) -> list[ApplianceOut]:
    result = await session.execute(select(Appliance).order_by(Appliance.created_at.desc()))
    return [ApplianceOut.model_validate(a) for a in result.scalars().all()]


@router.get("/{appliance_id}", response_model=ApplianceOut)
async def get_appliance(
    appliance_id: uuid.UUID,
    session: AsyncSession = Depends(get_rls_session),
) -> ApplianceOut:
    result = await session.execute(select(Appliance).where(Appliance.id == appliance_id))
    appliance = result.scalar_one_or_none()
    if appliance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appliance not found")
    return ApplianceOut.model_validate(appliance)


@router.post("/{appliance_id}/regenerate-secret")
async def regenerate_secret(
    appliance_id: uuid.UUID,
    user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> dict:
    """Generate a new device secret, store its hash, and return the plaintext once."""
    result = await session.execute(select(Appliance).where(Appliance.id == appliance_id))
    appliance = result.scalar_one_or_none()
    if appliance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appliance not found")
    new_secret = secrets.token_urlsafe(24)
    appliance.device_secret_hash = hash_password(new_secret)
    session.add(appliance)
    await session.flush()
    return {
        "appliance_id": str(appliance.id),
        "appliance_uid": appliance.appliance_uid,
        "device_secret": new_secret,
    }


@router.patch("/{appliance_id}", response_model=ApplianceOut)
async def update_appliance(
    appliance_id: uuid.UUID,
    data: ApplianceUpdate,
    session: AsyncSession = Depends(get_rls_session),
) -> ApplianceOut:
    result = await session.execute(select(Appliance).where(Appliance.id == appliance_id))
    appliance = result.scalar_one_or_none()
    if appliance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appliance not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(appliance, field, value)
    session.add(appliance)
    await session.flush()
    await session.refresh(appliance)
    return ApplianceOut.model_validate(appliance)
