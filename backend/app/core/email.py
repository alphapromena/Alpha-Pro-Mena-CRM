"""
Email delivery.

Transport is chosen by EMAIL_PROVIDER: "resend", "smtp" or "mock". Left unset, the
first provider with credentials wins and "mock" is the last resort.

The mock transport records messages in memory for local development and tests. It can
never run in production: an explicit EMAIL_PROVIDER=mock is rejected at settings load
time, and an implicit fall-through to mock raises EmailDeliveryError at send time. That
replaces the previous behaviour, where an unconfigured production environment silently
discarded every message and reported success to the user.

send_email returns an EmailResult rather than a bare bool so callers can log which
provider handled the message, record the provider's message id, and surface a real
error.
"""
import asyncio
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
import structlog

from app.config import get_settings
from app.core.exceptions import EmailDeliveryError

settings = get_settings()
logger = structlog.get_logger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"
SEND_TIMEOUT_SECONDS = 10.0

# Local in-memory store for development / test inspection
_DEV_MAILBOX: List[Dict[str, Any]] = []


@dataclass(frozen=True)
class EmailResult:
    """Outcome of a single send attempt."""
    ok: bool
    provider: str
    message_id: Optional[str] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        # Keeps `if await send_email(...)` working for any caller that still expects a bool.
        return self.ok


def get_dev_mailbox() -> List[Dict[str, Any]]:
    """Return in-memory dev emails (most recent first)."""
    return list(reversed(_DEV_MAILBOX))


def clear_dev_mailbox() -> None:
    """Clear in-memory dev emails."""
    _DEV_MAILBOX.clear()


# ─── Providers ────────────────────────────────────────────────────────────────

async def _send_via_resend(
    to_email: str,
    subject: str,
    text_content: str,
    html_content: Optional[str],
) -> EmailResult:
    """Deliver through the Resend HTTP API."""
    payload: Dict[str, Any] = {
        "from": settings.sender_address,
        "to": [to_email],
        "subject": subject,
        "text": text_content,
    }
    if html_content:
        payload["html"] = html_content

    try:
        async with httpx.AsyncClient(timeout=SEND_TIMEOUT_SECONDS) as http:
            response = await http.post(
                RESEND_ENDPOINT,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
            )
    except httpx.HTTPError as exc:
        return EmailResult(ok=False, provider="resend", error=f"transport error: {exc}")

    if response.status_code >= 400:
        # Resend returns a JSON body with a message; fall back to the raw text.
        detail: str
        try:
            body = response.json()
            detail = body.get("message") or body.get("error") or str(body)
        except Exception:
            detail = response.text[:300]
        return EmailResult(
            ok=False,
            provider="resend",
            error=f"HTTP {response.status_code}: {detail}",
        )

    message_id: Optional[str] = None
    try:
        message_id = response.json().get("id")
    except Exception:
        pass
    return EmailResult(ok=True, provider="resend", message_id=message_id)


def _smtp_send_blocking(
    to_email: str,
    subject: str,
    text_content: str,
    html_content: Optional[str],
) -> None:
    """The blocking part of an SMTP send. Runs in a worker thread."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.sender_address
    msg["To"] = to_email
    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    if html_content:
        msg.attach(MIMEText(html_content, "html", "utf-8"))

    server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=SEND_TIMEOUT_SECONDS)
    try:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.sender_address, [to_email], msg.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass


async def _send_via_smtp(
    to_email: str,
    subject: str,
    text_content: str,
    html_content: Optional[str],
) -> EmailResult:
    """
    Deliver through SMTP.

    smtplib is synchronous, so it is pushed to a worker thread rather than blocking
    the event loop for the duration of the connection.
    """
    try:
        await asyncio.to_thread(
            _smtp_send_blocking, to_email, subject, text_content, html_content
        )
    except Exception as exc:
        return EmailResult(ok=False, provider="smtp", error=str(exc))
    return EmailResult(ok=True, provider="smtp")


def _send_via_mock(record: Dict[str, Any]) -> EmailResult:
    """Record the message in memory. Development and test only."""
    _DEV_MAILBOX.append(record)
    if len(_DEV_MAILBOX) > 100:
        _DEV_MAILBOX.pop(0)
    return EmailResult(ok=True, provider="mock")


# ─── Entry point ──────────────────────────────────────────────────────────────

async def send_email(
    to_email: str,
    subject: str,
    text_content: str,
    html_content: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> EmailResult:
    """
    Send one email through the configured provider.

    Returns an EmailResult describing what happened. Raises EmailDeliveryError only
    when the environment is production and no real provider is configured, since that
    is a deployment fault the caller must surface rather than retry.
    """
    meta = meta or {}
    action = meta.get("action")
    provider = settings.resolved_email_provider
    record = {
        "to": to_email,
        "email": to_email,
        "subject": subject,
        "text": text_content,
        "html": html_content,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "token": meta.get("token"),
        "meta": meta,
    }

    if settings.app_env == "production" and not settings.email_delivery_available:
        logger.error(
            "email.no_provider_configured",
            to=to_email,
            action=action,
            provider=provider,
        )
        raise EmailDeliveryError(
            "Email delivery is not configured on this deployment. "
            "Set EMAIL_PROVIDER together with the matching credentials."
        )

    if provider == "resend":
        if not settings.resend_configured:
            result = EmailResult(
                ok=False,
                provider="resend",
                error="EMAIL_PROVIDER=resend but RESEND_API_KEY or EMAIL_FROM is missing.",
            )
        else:
            result = await _send_via_resend(to_email, subject, text_content, html_content)
    elif provider == "smtp":
        if not settings.smtp_configured:
            result = EmailResult(
                ok=False,
                provider="smtp",
                error="EMAIL_PROVIDER=smtp but SMTP_HOST is missing.",
            )
        else:
            result = await _send_via_smtp(to_email, subject, text_content, html_content)
    elif provider == "mock":
        result = _send_via_mock(record)
    else:
        result = EmailResult(
            ok=False,
            provider=provider,
            error=f"Unknown EMAIL_PROVIDER '{provider}'. Expected resend, smtp or mock.",
        )

    if result.ok:
        logger.info(
            "email.sent",
            to=to_email,
            subject=subject,
            action=action,
            provider=result.provider,
            message_id=result.message_id,
        )
    else:
        logger.error(
            "email.send_failed",
            to=to_email,
            subject=subject,
            action=action,
            provider=result.provider,
            error=result.error,
        )
    return result


def _link(path: str, token: str, to_email: str) -> str:
    """Build an absolute link into the frontend, encoding both query values."""
    return (
        f"{settings.frontend_url}{path}"
        f"?token={quote(token, safe='')}&email={quote(to_email, safe='')}"
    )


async def send_verification_email(to_email: str, recipient_name: str, token: str) -> EmailResult:
    """Send one-time expiring email verification link/token."""
    verify_url = _link("/verify-email", token, to_email)
    subject = f"Verify your {settings.app_name} account"
    text = (
        f"Hello {recipient_name},\n\n"
        f"Please verify your email address for your {settings.app_name} account.\n"
        f"Your verification code / token is:\n{token}\n\n"
        f"Or visit this URL to verify:\n{verify_url}\n\n"
        f"This token will expire in {settings.verification_token_expire_hours} hours and can only be used once.\n\n"
        f"If you did not request this, please contact your administrator."
    )
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
        <h2 style="color: #FF1E57; margin-bottom: 8px;">{settings.app_name}</h2>
        <h3 style="color: #0f172a; margin-top: 0;">Verify Your Email Address</h3>
        <p>Hello {recipient_name},</p>
        <p>Welcome to Alpha Pro MENA CRM. Please verify your company email address to activate full access to your workspace.</p>
        <div style="margin: 24px 0; text-align: center;">
            <a href="{verify_url}" style="background-color: #FF1E57; color: #ffffff; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: bold; display: inline-block;">
                Verify Email Address
            </a>
        </div>
        <p style="font-size: 12px; color: #64748b;">Verification code: <code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">{token}</code></p>
        <p style="font-size: 12px; color: #64748b;">This token will expire in {settings.verification_token_expire_hours} hours and becomes unusable after one use.</p>
    </div>
    """
    return await send_email(to_email, subject, text, html, meta={"action": "verify_email", "token": token})


async def send_password_reset_email(to_email: str, recipient_name: str, token: str) -> EmailResult:
    """Send secure password reset link/token."""
    reset_url = _link("/reset-password", token, to_email)
    subject = f"Password Reset Request — {settings.app_name}"
    text = (
        f"Hello {recipient_name},\n\n"
        f"We received a request to reset the password for your {settings.app_name} account.\n"
        f"Your reset code is:\n{token}\n\n"
        f"Or click here to reset your password:\n{reset_url}\n\n"
        f"This link expires in {settings.password_reset_token_expire_hours} hours.\n"
        f"If you did not request a password reset, you can safely ignore this email."
    )
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
        <h2 style="color: #FF1E57; margin-bottom: 8px;">{settings.app_name}</h2>
        <h3 style="color: #0f172a; margin-top: 0;">Password Reset Request</h3>
        <p>Hello {recipient_name},</p>
        <p>We received a request to reset your password. Click the button below to set a new password:</p>
        <div style="margin: 24px 0; text-align: center;">
            <a href="{reset_url}" style="background-color: #0f172a; color: #ffffff; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: bold; display: inline-block;">
                Reset Password
            </a>
        </div>
        <p style="font-size: 12px; color: #64748b;">Reset code: <code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">{token}</code></p>
        <p style="font-size: 12px; color: #64748b;">This link will expire in {settings.password_reset_token_expire_hours} hours. If you did not make this request, please contact IT immediately.</p>
    </div>
    """
    return await send_email(to_email, subject, text, html, meta={"action": "reset_password", "token": token})
