"""Reading query endpoints — DC, AC, and sensor time series with automatic resolution."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_rls_session, require_password_changed
from app.models.battery import Battery
from app.models.ac_channel import AcChannel
from app.models.rs485_sensor import Rs485Sensor
from app.models.user import User

router = APIRouter(prefix="/readings", tags=["readings"])

_NOW = lambda: datetime.now(timezone.utc)


# ── Schemas ────────────────────────────────────────────────────────────────────

class DcPoint(BaseModel):
    t: datetime
    v_avg: float
    v_min: float | None = None
    v_max: float | None = None
    i_avg: float
    i_min: float | None = None
    i_max: float | None = None
    p_avg: float
    energy_wh: float | None = None       # raw readings: cumulative meter total
    energy_delta_wh: float | None = None  # aggregate views: energy in bucket period
    alarm: int = 0
    resolution: str


class AcPoint(BaseModel):
    t: datetime
    v_avg: float
    v_min: float | None = None
    v_max: float | None = None
    i_avg: float
    p_avg: float
    freq_avg: float
    pf_avg: float
    energy_delta_wh: float | None = None
    resolution: str


class SensorPoint(BaseModel):
    t: datetime
    sensor_id: uuid.UUID
    sensor_type: str
    payload: dict[str, Any]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _resolution(from_dt: datetime, to_dt: datetime) -> str:
    span = to_dt - from_dt
    if span <= timedelta(hours=6):
        return "raw"
    if span <= timedelta(days=7):
        return "hourly"
    return "daily"


async def _get_battery(battery_id: uuid.UUID, user: User, session: AsyncSession) -> Battery:
    result = await session.execute(select(Battery).where(Battery.id == battery_id))
    bat = result.scalar_one_or_none()
    if bat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Battery not found")
    return bat


async def _get_channel(channel_id: uuid.UUID, user: User, session: AsyncSession) -> AcChannel:
    result = await session.execute(select(AcChannel).where(AcChannel.id == channel_id))
    ch = result.scalar_one_or_none()
    if ch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="AC channel not found")
    return ch


# ── DC endpoints ───────────────────────────────────────────────────────────────

@router.get("/dc/{battery_id}/latest", response_model=DcPoint)
async def dc_latest(
    battery_id: uuid.UUID,
    user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> DcPoint:
    bat = await _get_battery(battery_id, user, session)
    row = await session.execute(
        text("""
            SELECT time, voltage, current, power, energy_wh, alarm_flags
            FROM dc_readings
            WHERE battery_id = :bid AND client_id = :cid
            ORDER BY time DESC LIMIT 1
        """),
        {"bid": bat.id, "cid": bat.client_id},
    )
    r = row.mappings().one_or_none()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No readings yet")
    return DcPoint(
        t=r["time"],
        v_avg=float(r["voltage"]),
        i_avg=float(r["current"]),
        p_avg=float(r["power"]),
        energy_wh=float(r["energy_wh"]),
        alarm=int(r["alarm_flags"]),
        resolution="raw",
    )


@router.get("/dc/{battery_id}", response_model=list[DcPoint])
async def dc_range(
    battery_id: uuid.UUID,
    from_dt: Annotated[datetime | None, Query(alias="from")] = None,
    to_dt: Annotated[datetime | None, Query(alias="to")] = None,
    user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> list[DcPoint]:
    bat = await _get_battery(battery_id, user, session)
    now = _NOW()
    t0 = from_dt or (now - timedelta(hours=6))
    t1 = to_dt or now
    res = _resolution(t0, t1)

    if res == "raw":
        rows = await session.execute(
            text("""
                SELECT time AS t, voltage, current, power, energy_wh, alarm_flags
                FROM dc_readings
                WHERE battery_id = :bid AND client_id = :cid
                  AND time >= :t0 AND time <= :t1
                ORDER BY time ASC LIMIT 2000
            """),
            {"bid": bat.id, "cid": bat.client_id, "t0": t0, "t1": t1},
        )
        return [
            DcPoint(t=r["t"], v_avg=float(r["voltage"]), i_avg=float(r["current"]),
                    p_avg=float(r["power"]), energy_wh=float(r["energy_wh"]),
                    alarm=int(r["alarm_flags"]), resolution="raw")
            for r in rows.mappings()
        ]

    view = "dc_readings_hourly" if res == "hourly" else "dc_readings_daily"
    rows = await session.execute(
        text(f"""
            SELECT bucket AS t,
                   avg_voltage, min_voltage, max_voltage,
                   avg_current, min_current, max_current,
                   energy_delta_wh
            FROM {view}
            WHERE battery_id = :bid AND client_id = :cid
              AND bucket >= :t0 AND bucket <= :t1
            ORDER BY bucket ASC
        """),
        {"bid": bat.id, "cid": bat.client_id, "t0": t0, "t1": t1},
    )
    return [
        DcPoint(
            t=r["t"],
            v_avg=float(r["avg_voltage"] or 0),
            v_min=float(r["min_voltage"] or 0),
            v_max=float(r["max_voltage"] or 0),
            i_avg=float(r["avg_current"] or 0),
            i_min=float(r["min_current"] or 0),
            i_max=float(r["max_current"] or 0),
            p_avg=0.0,
            energy_delta_wh=float(r["energy_delta_wh"] or 0),
            resolution=res,
        )
        for r in rows.mappings()
    ]


# ── AC endpoints ───────────────────────────────────────────────────────────────

@router.get("/ac/{channel_id}/latest", response_model=AcPoint)
async def ac_latest(
    channel_id: uuid.UUID,
    user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> AcPoint:
    ch = await _get_channel(channel_id, user, session)
    row = await session.execute(
        text("""
            SELECT time, voltage, current, power, energy_wh, frequency, power_factor
            FROM ac_readings
            WHERE ac_channel_id = :cid AND client_id = :client_id
            ORDER BY time DESC LIMIT 1
        """),
        {"cid": ch.id, "client_id": ch.client_id},
    )
    r = row.mappings().one_or_none()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No readings yet")
    return AcPoint(
        t=r["time"],
        v_avg=float(r["voltage"]),
        i_avg=float(r["current"]),
        p_avg=float(r["power"]),
        freq_avg=float(r["frequency"]),
        pf_avg=float(r["power_factor"]),
        resolution="raw",
    )


@router.get("/ac/{channel_id}", response_model=list[AcPoint])
async def ac_range(
    channel_id: uuid.UUID,
    from_dt: Annotated[datetime | None, Query(alias="from")] = None,
    to_dt: Annotated[datetime | None, Query(alias="to")] = None,
    user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> list[AcPoint]:
    ch = await _get_channel(channel_id, user, session)
    now = _NOW()
    t0 = from_dt or (now - timedelta(hours=6))
    t1 = to_dt or now
    res = _resolution(t0, t1)

    if res == "raw":
        rows = await session.execute(
            text("""
                SELECT time AS t, voltage, current, power, frequency, power_factor
                FROM ac_readings
                WHERE ac_channel_id = :cid AND client_id = :client_id
                  AND time >= :t0 AND time <= :t1
                ORDER BY time ASC LIMIT 2000
            """),
            {"cid": ch.id, "client_id": ch.client_id, "t0": t0, "t1": t1},
        )
        return [
            AcPoint(t=r["t"], v_avg=float(r["voltage"]), i_avg=float(r["current"]),
                    p_avg=float(r["power"]), freq_avg=float(r["frequency"]),
                    pf_avg=float(r["power_factor"]), resolution="raw")
            for r in rows.mappings()
        ]

    view = "ac_readings_hourly" if res == "hourly" else "ac_readings_daily"
    rows = await session.execute(
        text(f"""
            SELECT bucket AS t,
                   avg_voltage, min_voltage, max_voltage,
                   avg_current, avg_power, avg_frequency, avg_power_factor,
                   energy_delta_wh
            FROM {view}
            WHERE ac_channel_id = :cid AND client_id = :client_id
              AND bucket >= :t0 AND bucket <= :t1
            ORDER BY bucket ASC
        """),
        {"cid": ch.id, "client_id": ch.client_id, "t0": t0, "t1": t1},
    )
    return [
        AcPoint(
            t=r["t"],
            v_avg=float(r["avg_voltage"] or 0),
            v_min=float(r["min_voltage"] or 0),
            v_max=float(r["max_voltage"] or 0),
            i_avg=float(r["avg_current"] or 0),
            p_avg=float(r["avg_power"] or 0),
            freq_avg=float(r["avg_frequency"] or 0),
            pf_avg=float(r["avg_power_factor"] or 0),
            energy_delta_wh=float(r["energy_delta_wh"] or 0),
            resolution=res,
        )
        for r in rows.mappings()
    ]


# ── Sensor endpoints ───────────────────────────────────────────────────────────

@router.get("/sensor/{sensor_id}/latest", response_model=SensorPoint)
async def sensor_latest(
    sensor_id: uuid.UUID,
    user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> SensorPoint:
    result = await session.execute(select(Rs485Sensor).where(Rs485Sensor.id == sensor_id))
    sensor = result.scalar_one_or_none()
    if sensor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sensor not found")
    row = await session.execute(
        text("""
            SELECT time, payload
            FROM sensor_readings
            WHERE sensor_id = :sid AND client_id = :cid
            ORDER BY time DESC LIMIT 1
        """),
        {"sid": sensor.id, "cid": sensor.client_id},
    )
    r = row.mappings().one_or_none()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No readings yet")
    return SensorPoint(
        t=r["time"],
        sensor_id=sensor.id,
        sensor_type=sensor.sensor_type,
        payload=dict(r["payload"]),
    )


@router.get("/sensor/{sensor_id}", response_model=list[SensorPoint])
async def sensor_range(
    sensor_id: uuid.UUID,
    from_dt: Annotated[datetime | None, Query(alias="from")] = None,
    to_dt: Annotated[datetime | None, Query(alias="to")] = None,
    user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> list[SensorPoint]:
    result = await session.execute(select(Rs485Sensor).where(Rs485Sensor.id == sensor_id))
    sensor = result.scalar_one_or_none()
    if sensor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sensor not found")
    now = _NOW()
    t0 = from_dt or (now - timedelta(hours=6))
    t1 = to_dt or now
    rows = await session.execute(
        text("""
            SELECT time, payload
            FROM sensor_readings
            WHERE sensor_id = :sid AND client_id = :cid
              AND time >= :t0 AND time <= :t1
            ORDER BY time ASC LIMIT 2000
        """),
        {"sid": sensor.id, "cid": sensor.client_id, "t0": t0, "t1": t1},
    )
    return [
        SensorPoint(
            t=r["time"],
            sensor_id=sensor.id,
            sensor_type=sensor.sensor_type,
            payload=dict(r["payload"]),
        )
        for r in rows.mappings()
    ]
