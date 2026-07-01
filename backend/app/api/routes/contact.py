import smtplib
from email.message import EmailMessage

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.core.config import get_settings

router = APIRouter(prefix="/contact", tags=["contact"])


class ContactForm(BaseModel):
    name: str
    email: EmailStr
    company: str = ""
    message: str


@router.post("", status_code=204)
async def submit_contact(form: ContactForm) -> None:
    settings = get_settings()
    if not settings.contact_email or not settings.smtp_host:
        raise HTTPException(503, "Contact form not configured on this server")

    msg = EmailMessage()
    msg["Subject"] = f"batmonai enquiry: {form.name}" + (f" — {form.company}" if form.company else "")
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = settings.contact_email
    msg["Reply-To"] = form.email
    msg.set_content(
        f"Name:    {form.name}\n"
        f"Email:   {form.email}\n"
        f"Company: {form.company or '—'}\n\n"
        f"Message:\n{form.message}\n"
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as s:
            if settings.smtp_tls:
                s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)
    except Exception as exc:
        raise HTTPException(502, f"Failed to send email: {exc}") from exc
