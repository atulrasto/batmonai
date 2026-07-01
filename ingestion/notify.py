"""Email + webhook notifications for rule-triggered events."""
import json
import logging
from email.mime.text import MIMEText

import aiosmtplib
import httpx

from config import Settings

log = logging.getLogger(__name__)

_NOTIFY_KINDS = {
    "mains_outage", "discharge_start",
    "low_voltage", "high_voltage",
    "high_temperature", "high_humidity",
    "h2_gas_alarm", "device_offline",
}

_SEVERITY_LABEL = {
    "info":     "Info",
    "warning":  "Warning",
    "critical": "CRITICAL",
}

_KIND_LABEL = {
    "mains_outage":     "Mains power outage detected",
    "discharge_start":  "Battery discharge started",
    "low_voltage":      "Low battery voltage",
    "high_voltage":     "High battery voltage",
    "high_temperature": "High temperature",
    "high_humidity":    "High humidity",
    "h2_gas_alarm":     "Hydrogen gas alarm",
    "device_offline":   "Device went offline",
}


async def notify_event(
    kind: str,
    severity: str,
    appliance_uid: str,
    client_email: str,
    detail: dict,
    settings: Settings,
    webhook_url: str = "",
) -> None:
    if kind not in _NOTIFY_KINDS:
        return

    await _send_email(kind, severity, appliance_uid, client_email, detail, settings)
    await _send_webhook(kind, severity, appliance_uid, detail, webhook_url)


async def _send_email(
    kind: str,
    severity: str,
    appliance_uid: str,
    client_email: str,
    detail: dict,
    settings: Settings,
) -> None:
    if not client_email or not settings.smtp_host:
        log.debug("SMTP not configured or no email — skipping notification for %s", kind)
        return

    label = _SEVERITY_LABEL.get(severity, severity.upper())
    subject = f"[batmonai] {label}: {_KIND_LABEL.get(kind, kind)}"
    detail_lines = "\n".join(f"  {k}: {v}" for k, v in detail.items())
    body = (
        f"{_KIND_LABEL.get(kind, kind)}\n"
        f"{'=' * 40}\n\n"
        f"Appliance : {appliance_uid}\n"
        f"Severity  : {severity.upper()}\n\n"
        f"Details:\n{detail_lines}\n\n"
        f"Log in to https://batmon.energymonai.com to review.\n"
    )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = client_email

    use_ssl = settings.smtp_port == 465
    use_starttls = settings.smtp_tls and not use_ssl

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=use_ssl,
            start_tls=use_starttls,
        )
        log.info("Notified %s about %s on %s", client_email, kind, appliance_uid)
    except Exception:
        log.exception("Failed to send notification email for %s", kind)


async def _send_webhook(
    kind: str,
    severity: str,
    appliance_uid: str,
    detail: dict,
    webhook_url: str,
) -> None:
    if not webhook_url:
        return

    payload = {
        "event": kind,
        "severity": severity,
        "appliance_uid": appliance_uid,
        "label": _KIND_LABEL.get(kind, kind),
        "detail": detail,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                webhook_url,
                content=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            log.info("Webhook fired for %s on %s → %s %s", kind, appliance_uid, webhook_url, resp.status_code)
    except Exception:
        log.exception("Webhook POST failed for %s on %s → %s", kind, appliance_uid, webhook_url)
