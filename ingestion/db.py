"""DB write operations — all via raw asyncpg (no SQLAlchemy ORM)."""
import logging
import uuid
from datetime import datetime, timezone

import asyncpg

from cache import ApplianceInfo
from schemas import AcChannelPayload, DcChannelPayload, EnvSensorPayload, TelemetryPayload

log = logging.getLogger(__name__)


async def insert_telemetry(
    payload: TelemetryPayload,
    info: ApplianceInfo,
    pool: asyncpg.Pool,
) -> None:
    """Insert dc_readings, ac_readings, sensor_readings and update last_seen_at."""
    now = datetime.now(timezone.utc)

    dc_rows = _build_dc_rows(payload, info)
    ac_rows = _build_ac_rows(payload, info)
    env_rows = _build_env_rows(payload, info)

    async with pool.acquire() as conn:
        async with conn.transaction():
            if dc_rows:
                await conn.executemany(
                    """
                    INSERT INTO dc_readings
                        (time, battery_id, client_id, voltage, current, power, energy_wh, alarm_flags, ingested_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    dc_rows,
                )

            if ac_rows:
                await conn.executemany(
                    """
                    INSERT INTO ac_readings
                        (time, ac_channel_id, client_id, voltage, current, power, energy_wh,
                         frequency, power_factor, ingested_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    ac_rows,
                )

            if env_rows:
                await conn.executemany(
                    """
                    INSERT INTO sensor_readings (time, sensor_id, client_id, payload, ingested_at)
                    VALUES ($1, $2, $3, $4::jsonb, $5)
                    """,
                    env_rows,
                )

            # Update last_seen_at — also resolves any open device_offline event
            await conn.execute(
                "UPDATE appliances SET last_seen_at = $1, updated_at = $1 WHERE id = $2",
                now,
                info.id,
            )
            await _resolve_offline_event(conn, info.id, info.client_id, now)


def _build_dc_rows(
    payload: TelemetryPayload, info: ApplianceInfo
) -> list[tuple]:
    rows = []
    for dc in payload.dc:
        batt = info.batteries.get(dc.battery_uid)
        if batt is None:
            log.warning("Unknown battery_uid %s in appliance %s", dc.battery_uid, info.appliance_uid)
            continue
        rows.append((
            payload.ts,
            batt.id,
            info.client_id,
            dc.v,
            dc.i,
            dc.p,
            dc.e,
            dc.alarm,
            datetime.now(timezone.utc),
        ))
    return rows


def _build_ac_rows(
    payload: TelemetryPayload, info: ApplianceInfo
) -> list[tuple]:
    rows = []
    for ac in payload.ac:
        ch = info.ac_channels.get(ac.channel_uid)
        if ch is None:
            log.warning("Unknown channel_uid %s in appliance %s", ac.channel_uid, info.appliance_uid)
            continue
        rows.append((
            payload.ts,
            ch.id,
            info.client_id,
            ac.v,
            ac.i,
            ac.p,
            ac.e,
            ac.freq,
            ac.pf,
            datetime.now(timezone.utc),
        ))
    return rows


def _build_env_rows(
    payload: TelemetryPayload, info: ApplianceInfo
) -> list[tuple]:
    import json
    rows = []
    for env in payload.env:
        sen = info.sensors.get(env.sensor_uid)
        if sen is None:
            log.warning("Unknown sensor_uid %s in appliance %s", env.sensor_uid, info.appliance_uid)
            continue
        payload_json = json.dumps(env.model_dump())
        rows.append((
            payload.ts,
            sen.id,
            info.client_id,
            payload_json,
            datetime.now(timezone.utc),
        ))
    return rows


async def _resolve_offline_event(
    conn: asyncpg.Connection,
    appliance_id: uuid.UUID,
    client_id: uuid.UUID,
    now: datetime,
) -> None:
    await conn.execute(
        """
        UPDATE events SET resolved_at = $1
        WHERE appliance_id = $2
          AND kind = 'device_offline'
          AND resolved_at IS NULL
        """,
        now,
        appliance_id,
    )


async def open_offline_event(
    appliance_id: uuid.UUID,
    client_id: uuid.UUID,
    pool: asyncpg.Pool,
) -> None:
    """Create a device_offline event if none is already open."""
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT id FROM events
            WHERE appliance_id = $1 AND kind = 'device_offline' AND resolved_at IS NULL
            LIMIT 1
            """,
            appliance_id,
        )
        if existing:
            return
        await conn.execute(
            """
            INSERT INTO events (client_id, appliance_id, kind, severity)
            VALUES ($1, $2, 'device_offline', 'warning')
            """,
            client_id,
            appliance_id,
        )
        log.info("Opened device_offline event for appliance %s", appliance_id)


async def check_stale_appliances(
    threshold_seconds: int,
    pool: asyncpg.Pool,
) -> None:
    """Timer-based offline detection: open events for appliances silent too long."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, client_id FROM appliances
            WHERE is_active = true
              AND last_seen_at IS NOT NULL
              AND last_seen_at < NOW() - ($1 || ' seconds')::INTERVAL
            """,
            str(threshold_seconds),
        )
    for row in rows:
        await open_offline_event(row["id"], row["client_id"], pool)
