import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_rls_session, require_password_changed
from app.core.uid import unique_battery_uid
from app.models.appliance import Appliance
from app.models.battery import Battery
from app.models.user import User
from app.schemas.battery import BatteryCreate, BatteryOut, BatteryUpdate

router = APIRouter(prefix="/batteries", tags=["batteries"])


def _resolve_client_id(data_client_id: uuid.UUID | None, user: User) -> uuid.UUID:
    if user.role == "superuser":
        if data_client_id is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="client_id required for superuser")
        return data_client_id
    return user.client_id  # type: ignore[return-value]


@router.post("/", response_model=BatteryOut, status_code=status.HTTP_201_CREATED)
async def create_battery(
    data: BatteryCreate,
    user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> BatteryOut:
    client_id = _resolve_client_id(data.client_id, user)
    app_result = await session.execute(select(Appliance).where(Appliance.id == data.appliance_id))
    appliance = app_result.scalar_one_or_none()
    if appliance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appliance not found")
    battery_uid = await unique_battery_uid(session, appliance.appliance_uid)
    battery = Battery(
        client_id=client_id,
        appliance_id=data.appliance_id,
        battery_uid=battery_uid,
        name=data.name,
        modbus_addr=data.modbus_addr,
        shunt_rating_a=data.shunt_rating_a,
        capacity_ah=data.capacity_ah,
        chemistry=data.chemistry,
        nominal_v=data.nominal_v,
    )
    session.add(battery)
    await session.flush()
    await session.refresh(battery)
    return BatteryOut.model_validate(battery)


@router.get("/", response_model=list[BatteryOut])
async def list_batteries(
    session: AsyncSession = Depends(get_rls_session),
) -> list[BatteryOut]:
    result = await session.execute(select(Battery).order_by(Battery.created_at.desc()))
    return [BatteryOut.model_validate(b) for b in result.scalars().all()]


@router.get("/{battery_id}", response_model=BatteryOut)
async def get_battery(
    battery_id: uuid.UUID,
    session: AsyncSession = Depends(get_rls_session),
) -> BatteryOut:
    result = await session.execute(select(Battery).where(Battery.id == battery_id))
    battery = result.scalar_one_or_none()
    if battery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Battery not found")
    return BatteryOut.model_validate(battery)


@router.patch("/{battery_id}", response_model=BatteryOut)
async def update_battery(
    battery_id: uuid.UUID,
    data: BatteryUpdate,
    session: AsyncSession = Depends(get_rls_session),
) -> BatteryOut:
    result = await session.execute(select(Battery).where(Battery.id == battery_id))
    battery = result.scalar_one_or_none()
    if battery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Battery not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(battery, field, value)
    session.add(battery)
    await session.flush()
    await session.refresh(battery)
    return BatteryOut.model_validate(battery)
