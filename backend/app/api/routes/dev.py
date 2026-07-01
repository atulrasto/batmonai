"""Developer utilities — simulator for generating fake telemetry (dev mode only)."""
import asyncio
import json
import random
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import require_password_changed
from app.core.database import AsyncSessionLocal
from app.models.user import User

router = APIRouter(prefix="/dev", tags=["dev"])


class SimRequest(BaseModel):
    appliance_id: str
    interval_s: int = 5


async def _sim_loop(appliance_id: str, interval_s: int) -> None:
    """Insert fake DC/AC readings on a fixed interval, simulating a charge/discharge cycle."""
    tick = 0
    aid = uuid.UUID(appliance_id)

    while True:
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # bypass RLS — also set current_client_id to a nil UUID so the
                    # RLS policy's OR clause doesn't crash on an empty-string→UUID cast.
                    await session.execute(text("SET LOCAL app.bypass_rls = 'true'"))
                    await session.execute(text(
                        "SET LOCAL app.current_client_id = '00000000-0000-0000-0000-000000000000'"
                    ))
                    now = datetime.now(timezone.utc)

                    bats = (
                        await session.execute(
                            text("""
                                SELECT id, client_id, nominal_v
                                FROM batteries
                                WHERE appliance_id = :aid AND is_active = true
                            """),
                            {"aid": aid},
                        )
                    ).mappings().all()

                    chs = (
                        await session.execute(
                            text("""
                                SELECT id, client_id
                                FROM ac_channels
                                WHERE appliance_id = :aid AND is_active = true
                            """),
                            {"aid": aid},
                        )
                    ).mappings().all()

                    sns = (
                        await session.execute(
                            text("""
                                SELECT id, client_id, sensor_type
                                FROM rs485_sensors
                                WHERE appliance_id = :aid AND is_active = true
                            """),
                            {"aid": aid},
                        )
                    ).mappings().all()

                    # 40-tick cycle: 30 ticks with mains, 10 without
                    mains_ok = (tick % 40) < 30

                    for bat in bats:
                        nominal = float(bat["nominal_v"])
                        if mains_ok:
                            v = nominal * 1.055 + random.uniform(-0.08, 0.08)
                            i = 2.5 + random.uniform(-0.3, 0.3)
                        else:
                            # voltage sags during discharge
                            sag = (tick % 40 - 30) * 0.015
                            v = nominal * 0.945 - sag + random.uniform(-0.04, 0.04)
                            i = -(3.5 + random.uniform(-0.4, 0.4))
                        p = round(abs(v * i), 1)
                        energy = round(1000.0 + tick * abs(i) * interval_s / 3600.0, 2)

                        await session.execute(
                            text("""
                                INSERT INTO dc_readings
                                  (time, battery_id, client_id, voltage, current,
                                   power, energy_wh, alarm_flags, ingested_at)
                                VALUES (:t, :bid, :cid, :v, :i, :p, :e, 0, :t)
                            """),
                            {
                                "t": now, "bid": bat["id"], "cid": bat["client_id"],
                                "v": round(v, 3), "i": round(i, 3), "p": p, "e": energy,
                            },
                        )

                    for ch in chs:
                        if mains_ok:
                            v = 230.0 + random.uniform(-3.0, 3.0)
                            i = 4.5 + random.uniform(-0.5, 0.5)
                            freq = 50.0 + random.uniform(-0.1, 0.1)
                            pf = 0.92 + random.uniform(-0.03, 0.03)
                            p = round(v * i * pf, 1)
                        else:
                            v = i = p = freq = pf = 0.0
                        energy = round(500.0 + tick * 0.03, 2)

                        await session.execute(
                            text("""
                                INSERT INTO ac_readings
                                  (time, ac_channel_id, client_id, voltage, current,
                                   power, energy_wh, frequency, power_factor, ingested_at)
                                VALUES (:t, :cid, :client_id, :v, :i, :p, :e, :freq, :pf, :t)
                            """),
                            {
                                "t": now, "cid": ch["id"], "client_id": ch["client_id"],
                                "v": round(v, 1), "i": round(i, 2),
                                "p": p, "e": energy,
                                "freq": round(freq, 2), "pf": round(pf, 3),
                            },
                        )

                    for sn in sns:
                        stype = sn["sensor_type"]
                        if stype == "temp_humidity":
                            payload = {
                                "temperature_c": round(25.0 + random.uniform(-3.0, 3.0), 1),
                                "humidity_pct": round(55.0 + random.uniform(-5.0, 5.0), 1),
                            }
                        elif stype == "gas_h2":
                            # simulate occasional brief H2 spikes
                            ppm = round(random.uniform(0, 8) + (20 if (tick % 60) == 55 else 0), 1)
                            payload = {"ppm": ppm, "alarm": ppm > 50}
                        else:
                            payload = {}

                        await session.execute(
                            text("""
                                INSERT INTO sensor_readings
                                  (time, sensor_id, client_id, payload, ingested_at)
                                VALUES (:t, :sid, :cid, CAST(:payload AS jsonb), :t)
                            """),
                            {
                                "t": now,
                                "sid": sn["id"],
                                "cid": sn["client_id"],
                                "payload": json.dumps(payload),
                            },
                        )

                    # keep appliance online indicator green
                    await session.execute(
                        text("UPDATE appliances SET last_seen_at = :t, updated_at = :t WHERE id = :aid"),
                        {"t": now, "aid": aid},
                    )

            tick += 1

        except asyncio.CancelledError:
            break
        except Exception as exc:
            print(f"[simulator:{appliance_id}] {exc}")

        try:
            await asyncio.sleep(interval_s)
        except asyncio.CancelledError:
            break


@router.post("/simulator/start", status_code=status.HTTP_200_OK)
async def simulator_start(
    body: SimRequest,
    request: Request,
    _user: User = Depends(require_password_changed),
) -> dict:
    tasks: dict[str, asyncio.Task] = request.app.state.sim_tasks
    aid = body.appliance_id
    existing = tasks.get(aid)
    if existing and not existing.done():
        return {"status": "already_running", "appliance_id": aid}
    tasks[aid] = asyncio.create_task(_sim_loop(aid, body.interval_s))
    return {"status": "started", "appliance_id": aid}


@router.post("/simulator/stop", status_code=status.HTTP_200_OK)
async def simulator_stop(
    body: SimRequest,
    request: Request,
    _user: User = Depends(require_password_changed),
) -> dict:
    tasks: dict[str, asyncio.Task] = request.app.state.sim_tasks
    aid = body.appliance_id
    task = tasks.pop(aid, None)
    if task and not task.done():
        task.cancel()
    return {"status": "stopped", "appliance_id": aid}


@router.get("/simulator/status")
async def simulator_status(
    request: Request,
    _user: User = Depends(require_password_changed),
) -> dict:
    tasks: dict[str, asyncio.Task] = request.app.state.sim_tasks
    active = [aid for aid, t in list(tasks.items()) if not t.done()]
    return {"active": active}
