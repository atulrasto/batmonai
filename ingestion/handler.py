"""MQTT message dispatch — telemetry and status (LWT) handling."""
import json
import logging

import asyncpg
from pydantic import ValidationError

import cache as appliance_cache
import db
import rules
import notify
from config import Settings
from schemas import TelemetryPayload

_settings = Settings()

log = logging.getLogger(__name__)


async def handle_message(
    topic: str,
    payload_bytes: bytes,
    pool: asyncpg.Pool,
) -> None:

    parts = topic.split("/")
    # Expected: batmon / {appliance_uid} / telemetry|status
    if len(parts) != 3 or parts[0] != "batmon":
        log.debug("Ignoring unexpected topic: %s", topic)
        return

    appliance_uid = parts[1]
    message_type = parts[2]

    if message_type == "telemetry":
        await _handle_telemetry(appliance_uid, payload_bytes, pool)
    elif message_type == "status":
        await _handle_status(appliance_uid, payload_bytes, pool)
    else:
        log.debug("Ignoring topic %s", topic)


async def _handle_telemetry(
    appliance_uid: str,
    payload_bytes: bytes,
    pool: asyncpg.Pool,
) -> None:
    try:
        raw = json.loads(payload_bytes)
    except json.JSONDecodeError:
        log.warning("Non-JSON telemetry from %s: %r", appliance_uid, payload_bytes[:120])
        return

    try:
        payload = TelemetryPayload.model_validate(raw)
    except ValidationError as exc:
        log.warning("Invalid telemetry schema from %s: %s", appliance_uid, exc)
        return

    if payload.appliance_uid != appliance_uid:
        log.warning(
            "appliance_uid mismatch: topic=%s payload=%s — rejecting",
            appliance_uid,
            payload.appliance_uid,
        )
        return

    info = await appliance_cache.resolve(appliance_uid, pool)
    if info is None:
        log.warning("Rejecting telemetry from unknown appliance: %s", appliance_uid)
        return

    try:
        await db.insert_telemetry(payload, info, pool)
        log.debug(
            "Ingested %d DC + %d AC + %d env readings from %s",
            len(payload.dc),
            len(payload.ac),
            len(payload.env),
            appliance_uid,
        )
    except Exception:
        log.exception("DB insert failed for appliance %s", appliance_uid)
        return

    # Rules engine — evaluate after successful insert
    try:
        opened = await rules.evaluate(payload, info, pool)
        for kind in opened:
            await notify.notify_event(
                kind=kind,
                severity="critical" if kind == "h2_gas_alarm" else "warning",
                appliance_uid=appliance_uid,
                client_email=info.client_email,
                detail={"appliance_uid": appliance_uid},
                settings=_settings,
                webhook_url=info.client_webhook_url,
            )
    except Exception:
        log.exception("Rules engine error for appliance %s", appliance_uid)


async def _handle_status(
    appliance_uid: str,
    payload_bytes: bytes,
    pool: asyncpg.Pool,
) -> None:
    status = payload_bytes.decode(errors="replace").strip().lower()
    log.info("Status message from %s: %s", appliance_uid, status)

    info = await appliance_cache.resolve(appliance_uid, pool)
    if info is None:
        log.debug("Status from unknown appliance %s — ignoring", appliance_uid)
        return

    if status == "offline":
        # LWT fired — device disconnected unexpectedly
        await db.open_offline_event(info.id, info.client_id, pool)
    elif status == "online":
        # Device reconnected — handled by telemetry insert (last_seen_at update)
        pass
