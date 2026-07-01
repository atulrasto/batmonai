import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_rls_session, require_password_changed
from app.core.uid import unique_channel_uid
from app.models.ac_channel import AcChannel
from app.models.appliance import Appliance
from app.models.user import User
from app.schemas.ac_channel import AcChannelCreate, AcChannelOut, AcChannelUpdate

router = APIRouter(prefix="/ac-channels", tags=["ac-channels"])


def _resolve_client_id(data_client_id: uuid.UUID | None, user: User) -> uuid.UUID:
    if user.role == "superuser":
        if data_client_id is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="client_id required for superuser")
        return data_client_id
    return user.client_id  # type: ignore[return-value]


@router.post("/", response_model=AcChannelOut, status_code=status.HTTP_201_CREATED)
async def create_ac_channel(
    data: AcChannelCreate,
    user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> AcChannelOut:
    client_id = _resolve_client_id(data.client_id, user)
    app_result = await session.execute(select(Appliance).where(Appliance.id == data.appliance_id))
    appliance = app_result.scalar_one_or_none()
    if appliance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appliance not found")
    channel_uid = await unique_channel_uid(session, appliance.appliance_uid, data.role)
    channel = AcChannel(
        client_id=client_id,
        appliance_id=data.appliance_id,
        channel_uid=channel_uid,
        name=data.name,
        modbus_addr=data.modbus_addr,
        role=data.role,
    )
    session.add(channel)
    await session.flush()
    await session.refresh(channel)
    return AcChannelOut.model_validate(channel)


@router.get("/", response_model=list[AcChannelOut])
async def list_ac_channels(
    session: AsyncSession = Depends(get_rls_session),
) -> list[AcChannelOut]:
    result = await session.execute(select(AcChannel).order_by(AcChannel.created_at.desc()))
    return [AcChannelOut.model_validate(c) for c in result.scalars().all()]


@router.get("/{channel_id}", response_model=AcChannelOut)
async def get_ac_channel(
    channel_id: uuid.UUID,
    session: AsyncSession = Depends(get_rls_session),
) -> AcChannelOut:
    result = await session.execute(select(AcChannel).where(AcChannel.id == channel_id))
    channel = result.scalar_one_or_none()
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AC channel not found")
    return AcChannelOut.model_validate(channel)


@router.patch("/{channel_id}", response_model=AcChannelOut)
async def update_ac_channel(
    channel_id: uuid.UUID,
    data: AcChannelUpdate,
    session: AsyncSession = Depends(get_rls_session),
) -> AcChannelOut:
    result = await session.execute(select(AcChannel).where(AcChannel.id == channel_id))
    channel = result.scalar_one_or_none()
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AC channel not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(channel, field, value)
    session.add(channel)
    await session.flush()
    await session.refresh(channel)
    return AcChannelOut.model_validate(channel)
