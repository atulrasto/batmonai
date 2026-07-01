"""batmonai ingestion service — MQTT → TimescaleDB."""
import asyncio
import logging
import ssl

import asyncpg
import aiomqtt

import db
from config import Settings
from handler import handle_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
log = logging.getLogger("ingestion")

_RECONNECT_DELAY_SECONDS = 5


def _build_tls_context(settings: Settings) -> ssl.SSLContext:
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=settings.mqtt_ca_cert)
    if settings.mqtt_tls_insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def _offline_check_loop(settings: Settings, pool: asyncpg.Pool) -> None:
    """Background task: timer-based device offline detection."""
    interval = settings.offline_threshold_seconds / 2
    while True:
        await asyncio.sleep(interval)
        try:
            await db.check_stale_appliances(settings.offline_threshold_seconds, pool)
        except Exception:
            log.exception("Error in offline check loop")


async def _mqtt_loop(settings: Settings, pool: asyncpg.Pool) -> None:
    """Main MQTT subscribe loop with auto-reconnect."""
    tls_ctx = _build_tls_context(settings)

    while True:
        try:
            log.info(
                "Connecting to MQTT broker %s:%d as %s",
                settings.mqtt_host,
                settings.mqtt_port_tls,
                settings.mqtt_username,
            )
            async with aiomqtt.Client(
                hostname=settings.mqtt_host,
                port=settings.mqtt_port_tls,
                username=settings.mqtt_username,
                password=settings.mqtt_password,
                tls_context=tls_ctx,
                will=aiomqtt.Will(
                    topic="batmon/ingestion/status",
                    payload=b"offline",
                    qos=1,
                    retain=False,
                ),
                keepalive=60,
            ) as client:
                log.info("MQTT connected. Subscribing to batmon/+/telemetry and batmon/+/status")
                await client.subscribe("batmon/+/telemetry", qos=1)
                await client.subscribe("batmon/+/status", qos=1)

                async for message in client.messages:
                    await handle_message(
                        topic=str(message.topic),
                        payload_bytes=bytes(message.payload),  # type: ignore[arg-type]
                        pool=pool,
                    )

        except aiomqtt.MqttError as exc:
            log.warning("MQTT disconnected (%s) — reconnecting in %ds", exc, _RECONNECT_DELAY_SECONDS)
            await asyncio.sleep(_RECONNECT_DELAY_SECONDS)
        except asyncio.CancelledError:
            log.info("MQTT loop cancelled")
            return


async def main() -> None:
    settings = Settings()
    log.info(
        "Connecting to postgres %s:%d db=%s",
        settings.postgres_host,
        settings.postgres_port,
        settings.postgres_db,
    )

    pool = await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
        min_size=2,
        max_size=10,
    )
    log.info("Postgres pool ready")

    await asyncio.gather(
        _mqtt_loop(settings, pool),
        _offline_check_loop(settings, pool),
    )


if __name__ == "__main__":
    asyncio.run(main())
