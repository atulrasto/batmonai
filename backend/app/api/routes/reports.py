"""Report generation endpoints — PDF download and email delivery."""
import uuid
from datetime import date, datetime, timezone, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_rls_session, require_password_changed
from app.core.config import Settings
from app.models.ac_channel import AcChannel
from app.models.appliance import Appliance
from app.models.battery import Battery
from app.models.site import Site
from app.models.user import User
from app.services import pdf as pdf_svc

router = APIRouter(prefix="/reports", tags=["reports"])
_settings = Settings()


# ── helpers ────────────────────────────────────────────────────────────────────

def _day_bounds(d: date) -> tuple[datetime, datetime]:
    """UTC midnight → next midnight for a calendar date."""
    t0 = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    t1 = t0 + timedelta(days=1)
    return t0, t1


async def _get_battery_ctx(battery_id: uuid.UUID, session: AsyncSession):
    """Return (battery, appliance, site) or raise 404."""
    bat = (await session.execute(select(Battery).where(Battery.id == battery_id))).scalar_one_or_none()
    if bat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Battery not found")
    app = (await session.execute(select(Appliance).where(Appliance.id == bat.appliance_id))).scalar_one_or_none()
    site = (await session.execute(select(Site).where(Site.id == app.site_id))).scalar_one_or_none() if app else None
    return bat, app, site


async def _get_channel_ctx(channel_id: uuid.UUID, session: AsyncSession):
    ch = (await session.execute(select(AcChannel).where(AcChannel.id == channel_id))).scalar_one_or_none()
    if ch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "AC channel not found")
    app = (await session.execute(select(Appliance).where(Appliance.id == ch.appliance_id))).scalar_one_or_none()
    site = (await session.execute(select(Site).where(Site.id == app.site_id))).scalar_one_or_none() if app else None
    return ch, app, site


async def _send_pdf_email(to: str, subject: str, body: str, pdf_bytes: bytes, filename: str) -> None:
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = _settings.smtp_from
    msg["To"] = to
    msg.attach(MIMEText(body, "plain"))
    att = MIMEApplication(pdf_bytes, _subtype="pdf")
    att.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(att)

    use_ssl = _settings.smtp_port == 465
    use_starttls = _settings.smtp_tls and not use_ssl

    await aiosmtplib.send(
        msg,
        hostname=_settings.smtp_host,
        port=_settings.smtp_port,
        username=_settings.smtp_user or None,
        password=_settings.smtp_password or None,
        use_tls=use_ssl,
        start_tls=use_starttls,
    )


# ── Battery report ─────────────────────────────────────────────────────────────

@router.get("/battery/{battery_id}/pdf")
async def battery_report_pdf(
    battery_id: uuid.UUID,
    report_date: date = Query(default_factory=lambda: (datetime.now(timezone.utc) - timedelta(days=1)).date()),
    _user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> Response:
    bat, app, site = await _get_battery_ctx(battery_id, session)
    t0, t1 = _day_bounds(report_date)

    hourly = await session.execute(text("""
        SELECT bucket,
               avg_voltage  AS avg_v, min_voltage AS min_v, max_voltage AS max_v,
               avg_current  AS avg_i, min_current AS min_i, max_current AS max_i,
               energy_delta_wh
        FROM dc_readings_hourly
        WHERE battery_id = :bid AND client_id = :cid
          AND bucket >= :t0 AND bucket < :t1
        ORDER BY bucket
    """), {"bid": bat.id, "cid": bat.client_id, "t0": t0, "t1": t1})
    hourly_rows = [dict(r) for r in hourly.mappings()]

    ev = await session.execute(text("""
        SELECT kind, severity, started_at, resolved_at
        FROM events
        WHERE appliance_id = :aid AND client_id = :cid
          AND started_at >= :t0 AND started_at < :t1
        ORDER BY started_at
    """), {"aid": bat.appliance_id, "cid": bat.client_id, "t0": t0, "t1": t1})
    events = [dict(r) for r in ev.mappings()]

    pdf_bytes = pdf_svc.battery_pdf(
        report_date=report_date,
        battery_uid=bat.battery_uid,
        appliance_uid=app.appliance_uid if app else "—",
        site_name=site.name if site else "—",
        nominal_v=float(bat.nominal_v),
        shunt_rating_a=bat.shunt_rating_a,
        hourly_rows=hourly_rows,
        events=events,
    )
    filename = f"battery_{bat.battery_uid}_{report_date.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/battery/{battery_id}/email")
async def battery_report_email(
    battery_id: uuid.UUID,
    report_date: date = Query(default_factory=lambda: (datetime.now(timezone.utc) - timedelta(days=1)).date()),
    _user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> dict:
    if not _settings.smtp_host:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "SMTP not configured")

    bat, app, site = await _get_battery_ctx(battery_id, session)
    t0, t1 = _day_bounds(report_date)

    hourly = await session.execute(text("""
        SELECT bucket,
               avg_voltage AS avg_v, min_voltage AS min_v, max_voltage AS max_v,
               avg_current AS avg_i, min_current AS min_i, max_current AS max_i,
               energy_delta_wh
        FROM dc_readings_hourly
        WHERE battery_id = :bid AND client_id = :cid
          AND bucket >= :t0 AND bucket < :t1
        ORDER BY bucket
    """), {"bid": bat.id, "cid": bat.client_id, "t0": t0, "t1": t1})
    hourly_rows = [dict(r) for r in hourly.mappings()]

    ev = await session.execute(text("""
        SELECT kind, severity, started_at, resolved_at
        FROM events
        WHERE appliance_id = :aid AND client_id = :cid
          AND started_at >= :t0 AND started_at < :t1
        ORDER BY started_at
    """), {"aid": bat.appliance_id, "cid": bat.client_id, "t0": t0, "t1": t1})
    events = [dict(r) for r in ev.mappings()]

    # Find client email
    from app.models.client import Client
    client_row = (await session.execute(select(Client).where(Client.id == bat.client_id))).scalar_one_or_none()
    to_email = client_row.primary_email if client_row else _settings.smtp_from

    pdf_bytes = pdf_svc.battery_pdf(
        report_date=report_date,
        battery_uid=bat.battery_uid,
        appliance_uid=app.appliance_uid if app else "—",
        site_name=site.name if site else "—",
        nominal_v=float(bat.nominal_v),
        shunt_rating_a=bat.shunt_rating_a,
        hourly_rows=hourly_rows,
        events=events,
    )
    filename = f"battery_{bat.battery_uid}_{report_date.isoformat()}.pdf"
    subject = f"[batmonai] Battery Report — {bat.battery_uid} — {report_date.isoformat()}"
    body = (
        f"Please find attached the daily battery report for {bat.battery_uid} "
        f"on {report_date.isoformat()}.\n\nAppliance: {app.appliance_uid if app else '—'}\n"
        f"Site: {site.name if site else '—'}\n"
    )
    await _send_pdf_email(to_email, subject, body, pdf_bytes, filename)
    return {"sent_to": to_email, "filename": filename}


# ── AC channel report ──────────────────────────────────────────────────────────

@router.get("/ac-channel/{channel_id}/pdf")
async def ac_channel_report_pdf(
    channel_id: uuid.UUID,
    report_date: date = Query(default_factory=lambda: (datetime.now(timezone.utc) - timedelta(days=1)).date()),
    _user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> Response:
    ch, app, site = await _get_channel_ctx(channel_id, session)
    t0, t1 = _day_bounds(report_date)

    hourly = await session.execute(text("""
        SELECT bucket,
               avg_voltage AS avg_v, avg_current AS avg_i, avg_power,
               avg_frequency AS avg_freq, avg_power_factor AS avg_pf,
               energy_delta_wh
        FROM ac_readings_hourly
        WHERE ac_channel_id = :cid AND client_id = :client_id
          AND bucket >= :t0 AND bucket < :t1
        ORDER BY bucket
    """), {"cid": ch.id, "client_id": ch.client_id, "t0": t0, "t1": t1})
    hourly_rows = [dict(r) for r in hourly.mappings()]

    ev = await session.execute(text("""
        SELECT kind, severity, started_at, resolved_at
        FROM events
        WHERE appliance_id = :aid AND client_id = :client_id
          AND started_at >= :t0 AND started_at < :t1
        ORDER BY started_at
    """), {"aid": ch.appliance_id, "client_id": ch.client_id, "t0": t0, "t1": t1})
    events = [dict(r) for r in ev.mappings()]

    pdf_bytes = pdf_svc.ac_channel_pdf(
        report_date=report_date,
        channel_uid=ch.channel_uid,
        appliance_uid=app.appliance_uid if app else "—",
        site_name=site.name if site else "—",
        role=ch.role,
        hourly_rows=hourly_rows,
        events=events,
    )
    filename = f"ac_{ch.channel_uid}_{report_date.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/ac-channel/{channel_id}/email")
async def ac_channel_report_email(
    channel_id: uuid.UUID,
    report_date: date = Query(default_factory=lambda: (datetime.now(timezone.utc) - timedelta(days=1)).date()),
    _user: User = Depends(require_password_changed),
    session: AsyncSession = Depends(get_rls_session),
) -> dict:
    if not _settings.smtp_host:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "SMTP not configured")

    ch, app, site = await _get_channel_ctx(channel_id, session)
    t0, t1 = _day_bounds(report_date)

    hourly = await session.execute(text("""
        SELECT bucket,
               avg_voltage AS avg_v, avg_current AS avg_i, avg_power,
               avg_frequency AS avg_freq, avg_power_factor AS avg_pf,
               energy_delta_wh
        FROM ac_readings_hourly
        WHERE ac_channel_id = :cid AND client_id = :client_id
          AND bucket >= :t0 AND bucket < :t1
        ORDER BY bucket
    """), {"cid": ch.id, "client_id": ch.client_id, "t0": t0, "t1": t1})
    hourly_rows = [dict(r) for r in hourly.mappings()]

    ev = await session.execute(text("""
        SELECT kind, severity, started_at, resolved_at
        FROM events
        WHERE appliance_id = :aid AND client_id = :client_id
          AND started_at >= :t0 AND started_at < :t1
        ORDER BY started_at
    """), {"aid": ch.appliance_id, "client_id": ch.client_id, "t0": t0, "t1": t1})
    events = [dict(r) for r in ev.mappings()]

    from app.models.client import Client
    client_row = (await session.execute(select(Client).where(Client.id == ch.client_id))).scalar_one_or_none()
    to_email = client_row.primary_email if client_row else _settings.smtp_from

    pdf_bytes = pdf_svc.ac_channel_pdf(
        report_date=report_date,
        channel_uid=ch.channel_uid,
        appliance_uid=app.appliance_uid if app else "—",
        site_name=site.name if site else "—",
        role=ch.role,
        hourly_rows=hourly_rows,
        events=events,
    )
    filename = f"ac_{ch.channel_uid}_{report_date.isoformat()}.pdf"
    subject = f"[batmonai] AC Report — {ch.channel_uid} — {report_date.isoformat()}"
    body = (
        f"Please find attached the daily AC channel report for {ch.channel_uid} "
        f"on {report_date.isoformat()}.\n\nAppliance: {app.appliance_uid if app else '—'}\n"
        f"Site: {site.name if site else '—'}\n"
    )
    await _send_pdf_email(to_email, subject, body, pdf_bytes, filename)
    return {"sent_to": to_email, "filename": filename}
