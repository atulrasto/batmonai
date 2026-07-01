"""
Stateless rules engine — evaluated after every telemetry insert.

Each rule follows the same pattern:
  - Condition met   → open event if none already open
  - Condition clear → resolve the open event

Thresholds:
  - Voltage:     batteries.low_v_threshold / high_v_threshold  (DB columns)
  - Temperature: rs485_sensors.config["high_temperature_c"]   (default 45°C)
  - Humidity:    rs485_sensors.config["high_humidity_pct"]    (default 80 %)
  - H2:          rs485_sensors.config["h2_alarm_ppm"]         (default 50 ppm)
  - Discharge:   any battery current < -0.5 A
  - AC present:  AC inverter_input voltage > 50 V
"""
import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg

from cache import ApplianceInfo
from schemas import TelemetryPayload

log = logging.getLogger(__name__)

# Minimum discharge current (A, negative) to count as discharging
_DISCHARGE_THRESHOLD = -0.5
# AC voltage below which mains is considered absent
_AC_ABSENT_V = 10.0
# AC voltage above which mains is considered present
_AC_PRESENT_V = 50.0


async def evaluate(
    payload: TelemetryPayload,
    info: ApplianceInfo,
    pool: asyncpg.Pool,
) -> list[str]:
    """
    Evaluate all rules for one telemetry batch.
    Returns list of event kinds that were newly opened (for notification).
    """
    opened: list[str] = []
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Fetch currently open events for this appliance (one DB call)
            open_rows = await conn.fetch(
                "SELECT kind FROM events WHERE appliance_id = $1 AND resolved_at IS NULL",
                info.id,
            )
            open_kinds: set[str] = {r["kind"] for r in open_rows}

            # ── Derive summary values from payload ────────────────────────────
            # Inverter input AC voltage (first inverter_input channel, or any AC if none)
            ac_v = 0.0
            for ac in payload.ac:
                ch = info.ac_channels.get(ac.channel_uid)
                if ch and ch.role == "inverter_input":
                    ac_v = ac.v
                    break
            if ac_v == 0.0 and payload.ac:
                ac_v = payload.ac[0].v

            mains_present = ac_v > _AC_PRESENT_V
            mains_absent  = ac_v < _AC_ABSENT_V

            # Any battery is discharging?
            any_discharging = any(dc.i < _DISCHARGE_THRESHOLD for dc in payload.dc)
            all_not_discharging = all(dc.i >= _DISCHARGE_THRESHOLD for dc in payload.dc)

            # ── Rule 1: mains_outage ──────────────────────────────────────────
            if mains_absent and any_discharging:
                k = await _open_event(
                    conn, info, "mains_outage", "warning",
                    {"ac_voltage": ac_v},
                    open_kinds, now,
                )
                if k: opened.append(k)
            elif mains_present and "mains_outage" in open_kinds:
                await _resolve(conn, info.id, "mains_outage", now)
                log.info("Resolved mains_outage for %s (AC back: %.1f V)", info.appliance_uid, ac_v)

            # ── Rule 2: discharge_start ───────────────────────────────────────
            if mains_absent and any_discharging:
                k = await _open_event(
                    conn, info, "discharge_start", "warning",
                    {"ac_voltage": ac_v,
                     "batteries": [{"uid": dc.battery_uid, "i": dc.i} for dc in payload.dc if dc.i < _DISCHARGE_THRESHOLD]},
                    open_kinds, now,
                )
                if k: opened.append(k)
            elif mains_present and all_not_discharging and "discharge_start" in open_kinds:
                await _resolve(conn, info.id, "discharge_start", now)
                log.info("Resolved discharge_start for %s", info.appliance_uid)

            # ── Rule 3: per-battery low_voltage / high_voltage ────────────────
            for dc in payload.dc:
                batt = info.batteries.get(dc.battery_uid)
                if batt is None:
                    continue
                uid_tag = dc.battery_uid
                detail_base = {"battery_uid": uid_tag, "voltage": dc.v}

                # Synthesise per-battery kind keys (append last 4 chars of uid for uniqueness)
                # We store kind in the events table as enum, so we use generic low_voltage /
                # high_voltage kind but put battery_uid in detail JSON.

                # Low voltage
                if dc.v > 0 and dc.v < batt.low_v_threshold:
                    k = await _open_event(
                        conn, info, "low_voltage", "warning",
                        {**detail_base, "threshold": batt.low_v_threshold},
                        open_kinds, now,
                        extra_filter=f"detail->>'battery_uid' = '{uid_tag}'",
                    )
                    if k: opened.append(k)
                elif dc.v >= batt.low_v_threshold and "low_voltage" in open_kinds:
                    await _resolve(conn, info.id, "low_voltage", now,
                                   extra_filter=f"detail->>'battery_uid' = '{uid_tag}'")

                # High voltage
                if dc.v > batt.high_v_threshold:
                    k = await _open_event(
                        conn, info, "high_voltage", "warning",
                        {**detail_base, "threshold": batt.high_v_threshold},
                        open_kinds, now,
                        extra_filter=f"detail->>'battery_uid' = '{uid_tag}'",
                    )
                    if k: opened.append(k)
                elif dc.v <= batt.high_v_threshold and "high_voltage" in open_kinds:
                    await _resolve(conn, info.id, "high_voltage", now,
                                   extra_filter=f"detail->>'battery_uid' = '{uid_tag}'")

            # ── Rule 4: env sensor rules ──────────────────────────────────────
            for env in payload.env:
                sen = info.sensors.get(env.sensor_uid)
                if sen is None:
                    continue
                env_data = env.model_dump()

                if sen.sensor_type == "temp_humidity":
                    temp   = env_data.get("temperature_c")
                    hum    = env_data.get("humidity_pct")
                    t_lim  = float(sen.config.get("high_temperature_c", 45.0))
                    h_lim  = float(sen.config.get("high_humidity_pct", 80.0))
                    uid_tag = env.sensor_uid

                    if temp is not None:
                        if temp > t_lim:
                            k = await _open_event(
                                conn, info, "high_temperature", "warning",
                                {"sensor_uid": uid_tag, "temperature_c": temp, "threshold": t_lim},
                                open_kinds, now,
                                extra_filter=f"detail->>'sensor_uid' = '{uid_tag}'",
                            )
                            if k: opened.append(k)
                        elif temp <= t_lim and "high_temperature" in open_kinds:
                            await _resolve(conn, info.id, "high_temperature", now,
                                           extra_filter=f"detail->>'sensor_uid' = '{uid_tag}'")

                    if hum is not None:
                        if hum > h_lim:
                            k = await _open_event(
                                conn, info, "high_humidity", "warning",
                                {"sensor_uid": uid_tag, "humidity_pct": hum, "threshold": h_lim},
                                open_kinds, now,
                                extra_filter=f"detail->>'sensor_uid' = '{uid_tag}'",
                            )
                            if k: opened.append(k)
                        elif hum <= h_lim and "high_humidity" in open_kinds:
                            await _resolve(conn, info.id, "high_humidity", now,
                                           extra_filter=f"detail->>'sensor_uid' = '{uid_tag}'")

                elif sen.sensor_type == "gas_h2":
                    ppm      = env_data.get("ppm", 0.0)
                    alarm    = env_data.get("alarm", False)
                    ppm_lim  = float(sen.config.get("h2_alarm_ppm", 50.0))
                    uid_tag  = env.sensor_uid

                    if alarm or ppm > ppm_lim:
                        k = await _open_event(
                            conn, info, "h2_gas_alarm", "critical",
                            {"sensor_uid": uid_tag, "ppm": ppm, "alarm": alarm, "threshold": ppm_lim},
                            open_kinds, now,
                            extra_filter=f"detail->>'sensor_uid' = '{uid_tag}'",
                        )
                        if k: opened.append(k)
                    elif not alarm and ppm <= ppm_lim and "h2_gas_alarm" in open_kinds:
                        await _resolve(conn, info.id, "h2_gas_alarm", now,
                                       extra_filter=f"detail->>'sensor_uid' = '{uid_tag}'")

    return opened


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _open_event(
    conn: asyncpg.Connection,
    info: ApplianceInfo,
    kind: str,
    severity: str,
    detail: dict,
    open_kinds: set[str],
    now: datetime,
    extra_filter: str = "",
) -> str | None:
    """Insert an event if one of this kind isn't already open. Returns kind if opened."""
    # Quick check against in-memory set first (avoids DB round-trip for already-open)
    if kind in open_kinds and not extra_filter:
        return None

    where = f"appliance_id = $1 AND kind = $2 AND resolved_at IS NULL"
    if extra_filter:
        where += f" AND {extra_filter}"

    existing = await conn.fetchrow(
        f"SELECT id FROM events WHERE {where} LIMIT 1",
        info.id, kind,
    )
    if existing:
        return None

    await conn.execute(
        """
        INSERT INTO events (client_id, appliance_id, kind, severity, detail, started_at)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6)
        """,
        info.client_id, info.id, kind, severity, json.dumps(detail), now,
    )
    log.info("Opened event %s for appliance %s  detail=%s", kind, info.appliance_uid, detail)
    return kind


async def _resolve(
    conn: asyncpg.Connection,
    appliance_id: uuid.UUID,
    kind: str,
    now: datetime,
    extra_filter: str = "",
) -> None:
    where = "appliance_id = $1 AND kind = $2 AND resolved_at IS NULL"
    if extra_filter:
        where += f" AND {extra_filter}"
    await conn.execute(
        f"UPDATE events SET resolved_at = $3 WHERE {where}",
        appliance_id, kind, now,
    )
