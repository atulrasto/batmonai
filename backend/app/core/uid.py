"""Auto-generate unique human-readable slugs and UIDs for all entities."""
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text or "item"


async def unique_site_slug(session: AsyncSession, client_id, base_name: str) -> str:
    from app.models.site import Site

    base = slugify(base_name)
    slug, n = base, 2
    while True:
        r = await session.execute(
            select(Site).where(Site.client_id == client_id, Site.slug == slug)
        )
        if r.scalar_one_or_none() is None:
            return slug
        slug = f"{base}-{n}"
        n += 1


async def unique_appliance_uid(session: AsyncSession, site_slug: str) -> str:
    from app.models.appliance import Appliance

    n = 1
    while True:
        uid = f"{site_slug}-gw{n}"
        r = await session.execute(
            select(Appliance).where(Appliance.appliance_uid == uid)
        )
        if r.scalar_one_or_none() is None:
            return uid
        n += 1


async def unique_battery_uid(session: AsyncSession, appliance_uid: str) -> str:
    from app.models.battery import Battery

    n = 1
    while True:
        uid = f"{appliance_uid}-bat{n}"
        r = await session.execute(
            select(Battery).where(Battery.battery_uid == uid)
        )
        if r.scalar_one_or_none() is None:
            return uid
        n += 1


async def unique_channel_uid(
    session: AsyncSession, appliance_uid: str, role: str
) -> str:
    from app.models.ac_channel import AcChannel

    prefix = {
        "inverter_input": "inv",
        "inverter_output": "inv-out",
        "load": "load",
    }.get(role, "ch")
    n = 1
    while True:
        uid = f"{appliance_uid}-{prefix}{n}"
        r = await session.execute(
            select(AcChannel).where(AcChannel.channel_uid == uid)
        )
        if r.scalar_one_or_none() is None:
            return uid
        n += 1


async def unique_sensor_uid(
    session: AsyncSession, appliance_uid: str, sensor_type: str
) -> str:
    from app.models.rs485_sensor import Rs485Sensor

    prefix = {"temp_humidity": "env", "gas_h2": "gas"}.get(sensor_type, "sensor")
    n = 1
    while True:
        uid = f"{appliance_uid}-{prefix}{n}"
        r = await session.execute(
            select(Rs485Sensor).where(Rs485Sensor.sensor_uid == uid)
        )
        if r.scalar_one_or_none() is None:
            return uid
        n += 1
