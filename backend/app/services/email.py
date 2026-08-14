"""Email delivery via the Brevo (Sendinblue) Transactional Email API.

The Brevo API key is read from settings and never logged or returned to the
frontend. Send failures return False (the caller decides how to react).
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


async def _send_transactional_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str,
) -> bool:
    if not settings.BREVO_API_KEY:
        logger.warning("BREVO_API_KEY not configured; skipping email send")
        return False

    payload = {
        "sender": {"email": settings.MAIL_FROM_EMAIL, "name": settings.MAIL_FROM_NAME},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
        "textContent": text_content,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                BREVO_SEND_URL,
                headers={
                    "api-key": settings.BREVO_API_KEY,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except Exception as exc:
        logger.warning("Brevo send error: %s", str(exc)[:200])
        return False

    if 200 <= resp.status_code < 300:
        return True

    logger.warning("Brevo send failed: HTTP %s: %s", resp.status_code, resp.text[:300])
    return False


async def send_verification_email(to_email: str, token: str) -> bool:
    link = f"{settings.FRONTEND_URL.rstrip('/')}/verify-email?token={token}"
    subject = "Verify your QuotePilot email"
    text = (
        "Welcome to QuotePilot.\n\n"
        "Please verify your email address by clicking the link below:\n\n"
        f"{link}\n"
    )
    html = (
        "<p style=\"font-family:Arial,sans-serif\">Welcome to QuotePilot.</p>"
        "<p style=\"font-family:Arial,sans-serif\">Please verify your email address.</p>"
        f'<p><a href="{link}" style="background-color:#2563EB;color:#ffffff;'
        'padding:10px 18px;text-decoration:none;border-radius:6px;'
        'font-family:Arial,sans-serif">Verify Email</a></p>'
        f'<p style="font-family:Arial,sans-serif;font-size:12px;color:#64748b">'
        f'If the button does not work, copy and paste this link into your browser:<br>{link}</p>'
    )
    return await _send_transactional_email(to_email, subject, html, text)


async def send_password_reset_email(to_email: str, token: str) -> bool:
    link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
    subject = "Reset your QuotePilot password"
    text = (
        "We received a request to reset your QuotePilot password.\n\n"
        "Click the link below to reset it:\n\n"
        f"{link}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    html = (
        '<p style="font-family:Arial,sans-serif">'
        "We received a request to reset your QuotePilot password.</p>"
        f'<p><a href="{link}" style="background-color:#2563EB;color:#ffffff;'
        'padding:10px 18px;text-decoration:none;border-radius:6px;'
        'font-family:Arial,sans-serif">Reset Password</a></p>'
        f'<p style="font-family:Arial,sans-serif;font-size:12px;color:#64748b">'
        f'If the button does not work, copy and paste this link into your browser:<br>{link}</p>'
        '<p style="font-family:Arial,sans-serif;font-size:12px;color:#64748b">'
        "If you did not request this, you can ignore this email.</p>"
    )
    return await _send_transactional_email(to_email, subject, html, text)
