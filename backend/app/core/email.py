"""
Email delivery service.
Handles verification emails and password reset emails.

Priority:
  1. Resend API  (RESEND_API_KEY is set)  — preferred, reliable transactional delivery
  2. SMTP        (SMTP_HOST is set)       — legacy fallback
  3. Dev mailbox (nothing configured)    — local dev / test, no real email sent

In development or test mode the dev mailbox is always used regardless of
which backend is configured, so real emails are never sent during CI.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import structlog
from app.config import get_settings

settings = get_settings()
logger = structlog.get_logger(__name__)

# Local in-memory store for development / test inspection
_DEV_MAILBOX: List[Dict[str, Any]] = []


def get_dev_mailbox() -> List[Dict[str, Any]]:
    """Return in-memory dev emails (most recent first)."""
    return list(reversed(_DEV_MAILBOX))


def clear_dev_mailbox() -> None:
    """Clear in-memory dev emails."""
    _DEV_MAILBOX.clear()


async def send_email(
    to_email: str,
    subject: str,
    text_content: str,
    html_content: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Send an email.
    Routes to Resend → SMTP → dev mailbox in priority order.
    Dev/test environments always use the dev mailbox.
    """
    msg_record = {
        "to": to_email,
        "email": to_email,
        "subject": subject,
        "text": text_content,
        "html": html_content,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "token": meta.get("token") if meta else None,
        "meta": meta or {},
    }

    # Always use dev mailbox in dev/test — never send real emails during CI
    if not settings.email_configured or settings.app_env in ("development", "test"):
        _DEV_MAILBOX.append(msg_record)
        if len(_DEV_MAILBOX) > 100:
            _DEV_MAILBOX.pop(0)
        logger.info(
            "email.mock_delivered",
            to=to_email,
            subject=subject,
            action=meta.get("action") if meta else None,
        )
        return True

    # ── Resend (preferred) ───────────────────────────────────────────────────
    if settings.resend_configured:
        return await _send_via_resend(to_email, subject, text_content, html_content, meta)

    # ── SMTP (legacy fallback) ───────────────────────────────────────────────
    return await _send_via_smtp(to_email, subject, text_content, html_content, meta)


async def _send_via_resend(
    to_email: str,
    subject: str,
    text_content: str,
    html_content: Optional[str],
    meta: Optional[Dict[str, Any]],
) -> bool:
    """Send via Resend API."""
    try:
        import resend  # lazy import — only needed when Resend is configured

        resend.api_key = settings.resend_api_key

        params: Dict[str, Any] = {
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": subject,
            "text": text_content,
        }
        if html_content:
            params["html"] = html_content

        resend.Emails.send(params)
        logger.info(
            "email.resend_sent",
            to=to_email,
            subject=subject,
            action=meta.get("action") if meta else None,
        )
        return True
    except Exception as exc:
        logger.error("email.resend_failed", to=to_email, error=str(exc))
        return False


async def _send_via_smtp(
    to_email: str,
    subject: str,
    text_content: str,
    html_content: Optional[str],
    meta: Optional[Dict[str, Any]],
) -> bool:
    """Send via raw SMTP (legacy fallback)."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from_email
        msg["To"] = to_email

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        if html_content:
            msg.attach(MIMEText(html_content, "html", "utf-8"))

        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from_email, [to_email], msg.as_string())
        server.quit()
        logger.info("email.smtp_sent", to=to_email, subject=subject)
        return True
    except Exception as exc:
        logger.error("email.smtp_failed", to=to_email, error=str(exc))
        return False


async def send_verification_email(to_email: str, recipient_name: str, token: str) -> bool:
    """Send one-time expiring email verification link/token."""
    verify_url = f"{settings.frontend_url}/verify-email?token={token}&email={to_email}"
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


async def send_password_reset_email(to_email: str, recipient_name: str, token: str) -> bool:
    """Send secure password reset link/token."""
    reset_url = f"{settings.frontend_url}/reset-password?token={token}&email={to_email}"
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