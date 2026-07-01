"""Appliance resolution cache — maps appliance_uid to DB IDs with TTL."""
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

log = logging.getLogger(__name__)

_TTL_SECONDS = 300  # 5 minutes


@dataclass
class BatteryInfo:
    id: uuid.UUID
    battery_uid: str
    modbus_addr: int
    nominal_v: float
    low_v_threshold: float = 11.5
    high_v_threshold: float = 14.5


@dataclass
class AcChannelInfo:
    id: uuid.UUID
    channel_uid: str
    modbus_addr: int
    role: str = "inverter_input"


@dataclass
class SensorInfo:
    id: uuid.UUID
    sensor_uid: str
    sensor_type: str
    modbus_addr: int
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApplianceInfo:
    id: uuid.UUID
    client_id: uuid.UUID
    appliance_uid: str
    client_email: str = ""
    client_webhook_url: str = ""
    batteries: dict[str, BatteryInfo] = field(default_factory=dict)
    ac_channels: dict[str, AcChannelInfo] = field(default_factory=dict)
    sensors: dict[str, SensorInfo] = field(default_factory=dict)
    _fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_stale(self) -> bool:
        return (datetime.now(timezone.utc) - self._fetched_at) > timedelta(seconds=_TTL_SECONDS)


_cache: dict[str, ApplianceInfo] = {}
_lock = asyncio.Lock()


async def resolve(appliance_uid: str, pool: asyncpg.Pool) -> ApplianceInfo | None:
    async with _lock:
        cached = _cache.get(appliance_uid)
        if cached and not cached.is_stale():
            return cached

    info = await _fetch(appliance_uid, pool)
    if info:
        async with _lock:
            _cache[appliance_uid] = info
    return info


def invalidate(appliance_uid: str) -> None:
    _cache.pop(appliance_uid, None)


async def _fetch(appliance_uid: str, pool: asyncpg.Pool) -> ApplianceInfo | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT a.id, a.client_id, c.primary_email, c.webhook_url
            FROM appliances a
            JOIN clients c ON c.id = a.client_id
            WHERE a.appliance_uid = $1 AND a.is_active = true
            """,
            appliance_uid,
        )
        if row is None:
            log.warning("Unknown or inactive appliance: %s", appliance_uid)
            return None

        info = ApplianceInfo(
            id=row["id"],
            client_id=row["client_id"],
            appliance_uid=appliance_uid,
            client_email=row["primary_email"] or "",
            client_webhook_url=row["webhook_url"] or "",
        )

        batt_rows = await conn.fetch(
            """
            SELECT id, battery_uid, modbus_addr,
                   nominal_v::float, low_v_threshold::float, high_v_threshold::float
            FROM batteries
            WHERE appliance_id = $1 AND is_active = true
            """,
            row["id"],
        )
        for b in batt_rows:
            info.batteries[b["battery_uid"]] = BatteryInfo(
                id=b["id"],
                battery_uid=b["battery_uid"],
                modbus_addr=b["modbus_addr"],
                nominal_v=b["nominal_v"],
                low_v_threshold=b["low_v_threshold"],
                high_v_threshold=b["high_v_threshold"],
            )

        ch_rows = await conn.fetch(
            "SELECT id, channel_uid, modbus_addr, role FROM ac_channels "
            "WHERE appliance_id = $1 AND is_active = true",
            row["id"],
        )
        for c in ch_rows:
            info.ac_channels[c["channel_uid"]] = AcChannelInfo(
                id=c["id"],
                channel_uid=c["channel_uid"],
                modbus_addr=c["modbus_addr"],
                role=c["role"],
            )

        sen_rows = await conn.fetch(
            "SELECT id, sensor_uid, sensor_type, modbus_addr, config::text FROM rs485_sensors "
            "WHERE appliance_id = $1 AND is_active = true",
            row["id"],
        )
        for s in sen_rows:
            import json
            cfg = json.loads(s["config"] or "{}")
            info.sensors[s["sensor_uid"]] = SensorInfo(
                id=s["id"],
                sensor_uid=s["sensor_uid"],
                sensor_type=s["sensor_type"],
                modbus_addr=s["modbus_addr"],
                config=cfg,
            )

    log.debug(
        "Resolved appliance %s: %d batteries, %d channels, %d sensors",
        appliance_uid,
        len(info.batteries),
        len(info.ac_channels),
        len(info.sensors),
    )
    return info
