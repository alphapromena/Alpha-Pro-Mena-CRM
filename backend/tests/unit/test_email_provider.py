"""
Email provider selection, the production guards, and the transports themselves.

These cover the failure the audit called C1: production had no SMTP configured, so
every send took the mock branch, discarded the message, and returned success.
"""
import httpx
import pytest
from pydantic import ValidationError as PydanticValidationError

from app.config import Settings
from app.core import email as email_module
from app.core.email import EmailResult, clear_dev_mailbox, get_dev_mailbox, send_email
from app.core.exceptions import EmailDeliveryError

# database_url is declared with a validation_alias, so it must be supplied under the
# alias name; passing "database_url" is silently ignored and the ambient test env leaks in.
PROD_BASE = {
    "app_secret_key": "x" * 40,
    "jwt_secret_key": "y" * 40,
    "DATABASE_URL": "postgresql://user:pw@db.example.com/crm",
    "frontend_url": "https://crm.example.com",
}


def _settings(**overrides) -> Settings:
    """Build a Settings instance without reading the ambient environment."""
    return Settings(**{**PROD_BASE, **overrides})


# ─── Provider selection ───────────────────────────────────────────────────────

def test_resend_credentials_select_resend():
    s = _settings(app_env="development", resend_api_key="re_test", email_from="no-reply@example.com")
    assert s.resolved_email_provider == "resend"
    assert s.resend_configured is True
    assert s.email_delivery_available is True


def test_smtp_host_selects_smtp_when_resend_absent():
    s = _settings(app_env="development", smtp_host="smtp.example.com")
    assert s.resolved_email_provider == "smtp"
    assert s.email_delivery_available is True


def test_nothing_configured_falls_back_to_mock():
    s = _settings(app_env="development")
    assert s.resolved_email_provider == "mock"
    # Mock cannot deliver to a real inbox, and must not be counted as if it could.
    assert s.email_delivery_available is False


def test_explicit_provider_overrides_inference():
    """An explicit choice must win, so a misconfiguration fails loudly instead of downgrading."""
    s = _settings(
        app_env="development",
        email_provider="smtp",
        resend_api_key="re_test",
        email_from="no-reply@example.com",
    )
    assert s.resolved_email_provider == "smtp"


def test_email_from_takes_precedence_over_legacy_smtp_from():
    s = _settings(app_env="development", email_from="new@example.com", smtp_from_email="old@example.com")
    assert s.sender_address == "new@example.com"


def test_sender_falls_back_to_smtp_from_email():
    s = _settings(app_env="development", smtp_from_email="old@example.com")
    assert s.sender_address == "old@example.com"


# ─── Production guards at settings load ───────────────────────────────────────

def test_production_rejects_explicit_mock_provider():
    with pytest.raises((PydanticValidationError, ValueError)) as exc:
        _settings(app_env="production", email_provider="mock")
    assert "mock" in str(exc.value).lower()


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://crm.example.com",       # not https
        "https://localhost:5173",       # localhost
        "https://127.0.0.1",            # loopback
        "http://localhost:5173",        # the shipped default
        "",                             # unset
    ],
)
def test_production_rejects_unusable_frontend_url(bad_url):
    """Every email link is built from this, so it is enforced at load time."""
    with pytest.raises((PydanticValidationError, ValueError)):
        _settings(app_env="production", frontend_url=bad_url)


def test_production_accepts_a_real_https_frontend_url():
    s = _settings(app_env="production", frontend_url="https://crm.example.com")
    assert s.frontend_url == "https://crm.example.com"


def test_trailing_slash_is_stripped_so_links_do_not_double_up():
    s = _settings(app_env="development", frontend_url="https://crm.example.com/")
    assert s.frontend_url == "https://crm.example.com"


# ─── send_email behaviour ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_production_without_a_provider_raises_instead_of_faking_success(monkeypatch):
    """
    The regression that motivated this work: an unconfigured production environment
    used to append to an in-memory list and return True.
    """
    monkeypatch.setattr(email_module, "settings", _settings(app_env="production"))
    clear_dev_mailbox()

    with pytest.raises(EmailDeliveryError):
        await send_email("someone@example.com", "Subject", "Body")

    # Nothing was quietly stashed in the mock mailbox either.
    assert get_dev_mailbox() == []


@pytest.mark.asyncio
async def test_mock_provider_records_the_message_outside_production(monkeypatch):
    monkeypatch.setattr(email_module, "settings", _settings(app_env="development"))
    clear_dev_mailbox()

    result = await send_email("dev@example.com", "Hello", "Body", meta={"token": "abc"})

    assert result.ok is True
    assert result.provider == "mock"
    messages = get_dev_mailbox()
    assert len(messages) == 1
    assert messages[0]["to"] == "dev@example.com"
    assert messages[0]["token"] == "abc"


def _mock_resend(monkeypatch, handler):
    """
    Point the Resend transport at an in-process handler instead of the network.

    The real class is captured before patching: email_module.httpx is the global
    httpx module, so a factory that called httpx.AsyncClient after the patch would
    call itself.
    """
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        return real_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(email_module.httpx, "AsyncClient", factory)


@pytest.mark.asyncio
async def test_resend_success_returns_the_provider_message_id(monkeypatch):
    monkeypatch.setattr(
        email_module,
        "settings",
        _settings(app_env="production", email_provider="resend",
                  resend_api_key="re_test", email_from="no-reply@example.com"),
    )
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"id": "msg_12345"})

    _mock_resend(monkeypatch, handler)

    result = await send_email("user@example.com", "Subject", "Body", "<p>Body</p>")

    assert isinstance(result, EmailResult)
    assert result.ok is True
    assert result.provider == "resend"
    assert result.message_id == "msg_12345"
    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["auth"] == "Bearer re_test"


@pytest.mark.asyncio
async def test_resend_http_error_is_reported_not_swallowed(monkeypatch):
    monkeypatch.setattr(
        email_module,
        "settings",
        _settings(app_env="production", email_provider="resend",
                  resend_api_key="re_bad", email_from="no-reply@example.com"),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"message": "Invalid from address"})

    _mock_resend(monkeypatch, handler)

    result = await send_email("user@example.com", "Subject", "Body")

    assert result.ok is False
    assert result.provider == "resend"
    assert "422" in result.error
    assert "Invalid from address" in result.error


@pytest.mark.asyncio
async def test_resend_transport_failure_is_reported(monkeypatch):
    monkeypatch.setattr(
        email_module,
        "settings",
        _settings(app_env="production", email_provider="resend",
                  resend_api_key="re_test", email_from="no-reply@example.com"),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _mock_resend(monkeypatch, handler)

    result = await send_email("user@example.com", "Subject", "Body")

    assert result.ok is False
    assert result.provider == "resend"
    assert "transport error" in result.error


@pytest.mark.asyncio
async def test_email_result_is_falsy_on_failure():
    """Callers that still treat the result as a bool keep working."""
    assert not EmailResult(ok=False, provider="resend", error="nope")
    assert EmailResult(ok=True, provider="resend")


# ─── Link construction ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verification_link_encodes_the_address_and_uses_frontend_url(monkeypatch):
    monkeypatch.setattr(
        email_module,
        "settings",
        _settings(app_env="development", frontend_url="https://crm.example.com"),
    )
    clear_dev_mailbox()

    await email_module.send_verification_email("first+tag@example.com", "First", "tok en/value")

    body = get_dev_mailbox()[0]["text"]
    assert "https://crm.example.com/verify-email?token=" in body
    # A plus sign in an address must survive the round trip as %2B, not become a space.
    assert "email=first%2Btag%40example.com" in body
    assert "token=tok%20en%2Fvalue" in body
    assert "localhost" not in body


@pytest.mark.asyncio
async def test_reset_link_points_at_the_reset_route(monkeypatch):
    monkeypatch.setattr(
        email_module,
        "settings",
        _settings(app_env="development", frontend_url="https://crm.example.com"),
    )
    clear_dev_mailbox()

    await email_module.send_password_reset_email("user@example.com", "User", "resettoken")

    body = get_dev_mailbox()[0]["text"]
    assert "https://crm.example.com/reset-password?token=resettoken" in body
