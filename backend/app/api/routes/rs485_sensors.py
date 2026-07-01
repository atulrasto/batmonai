import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_rls_session, require_password_changed
from app.core.uid import unique_sensor_uid
from app.models.appliance import Appliance
from app.models.rs485_sensor import Rs485Sensor
from app.models.user import User
from app.schemas.rs485_sensor import Rs485SensorCreate, Rs485SensorOut, Rs485SensorUpdate

router = APIRouter(prefix="/sensors", tags=["sensors"])


def _resolve_client_id(data_client_id: uuid.UUID | None, user: User) -> uuid.UUID:
    if user.role == "superuser":
        if data_client_id is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="client_id required for superuser")
        return data_client_id
    return user.client_id  # type: ignore[return-value]


@router.post("/", response_model=Rs485SensorOut, status_code=status.HTTP_201_CREATED)
async def create_sensor(
    data: Rs485SensorCreate,
    user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> Rs485SensorOut:
    client_id = _resolve_client_id(data.client_id, user)
    app_result = await session.execute(select(Appliance).where(Appliance.id == data.appliance_id))
    appliance = app_result.scalar_one_or_none()
    if appliance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appliance not found")
    sensor_uid = await unique_sensor_uid(session, appliance.appliance_uid, data.sensor_type)
    sensor = Rs485Sensor(
        client_id=client_id,
        appliance_id=data.appliance_id,
        sensor_uid=sensor_uid,
        sensor_type=data.sensor_type,
        modbus_addr=data.modbus_addr,
        name=data.name,
        config=data.config,
    )
    session.add(sensor)
    await session.flush()
    await session.refresh(sensor)
    return Rs485SensorOut.model_validate(sensor)


@router.get("/", response_model=list[Rs485SensorOut])
async def list_sensors(
    session: AsyncSession = Depends(get_rls_session),
) -> list[Rs485SensorOut]:
    result = await session.execute(select(Rs485Sensor).order_by(Rs485Sensor.created_at.desc()))
    return [Rs485SensorOut.model_validate(s) for s in result.scalars().all()]


@router.get("/{sensor_id}", response_model=Rs485SensorOut)
async def get_sensor(
    sensor_id: uuid.UUID,
    session: AsyncSession = Depends(get_rls_session),
) -> Rs485SensorOut:
    result = await session.execute(select(Rs485Sensor).where(Rs485Sensor.id == sensor_id))
    sensor = result.scalar_one_or_none()
    if sensor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found")
    return Rs485SensorOut.model_validate(sensor)


@router.patch("/{sensor_id}", response_model=Rs485SensorOut)
async def update_sensor(
    sensor_id: uuid.UUID,
    data: Rs485SensorUpdate,
    session: AsyncSession = Depends(get_rls_session),
) -> Rs485SensorOut:
    result = await session.execute(select(Rs485Sensor).where(Rs485Sensor.id == sensor_id))
    sensor = result.scalar_one_or_none()
    if sensor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(sensor, field, value)
    session.add(sensor)
    await session.flush()
    await session.refresh(sensor)
    return Rs485SensorOut.model_validate(sensor)
