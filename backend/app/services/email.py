import logging

from app.core.config import get_settings

log = logging.getLogger(__name__)
_settings = get_settings()


async def send_client_welcome(email: str, temp_password: str, client_name: str) -> None:
    """Send welcome email with temporary password to a new client user."""
    if not _settings.smtp_host:
        log.warning(
            "SMTP not configured — skipping welcome email to %s (temp_password=%s)",
            email,
            temp_password,
        )
        return
    try:
        import aiosmtplib
        from email.mime.text import MIMEText

        body = (
            f"Welcome to batmonai, {client_name}!\n\n"
            f"Your login: {email}\n"
            f"Temporary password: {temp_password}\n\n"
            "Please log in and change your password on first login.\n\n"
            "https://batmon.energymonai.com\n"
        )
        msg = MIMEText(body)
        msg["Subject"] = "Your batmonai account — set your password"
        msg["From"] = _settings.smtp_from
        msg["To"] = email

        # Port 465 = direct SSL; port 587 = STARTTLS.
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
        log.info("Welcome email sent to %s", email)
    except Exception:
        log.exception("Failed to send welcome email to %s", email)
