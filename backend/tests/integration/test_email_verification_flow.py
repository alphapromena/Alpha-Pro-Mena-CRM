"""
Email verification lifecycle.

Covers the production incident where every pre-existing account was locked out at
/verify-email: the email_verified column landed with DEFAULT FALSE, the router
redirects unverified users to that page, and nothing on the login or reset paths ever
sent the code the page asks for.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.auth.service import AuthService
from app.core.security import generate_secure_token, hash_password, hash_token, normalize_email
from app.models.user import User, UserRole


def make_user(prefix="verif", password="OldPassword123!", **kwargs) -> User:
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@alphapromena.com"
    defaults = dict(
        email=email,
        normalized_email=normalize_email(email),
        first_name="Verif",
        last_name="Tester",
        password_hash=hash_password(password),
        role=UserRole.SALES_USER,
        is_active=True,
        is_locked=False,
        login_attempts=0,
        must_change_password=False,
        email_verified=False,
    )
    defaults.update(kwargs)
    return User(**defaults)


# ─── A completed reset proves mailbox ownership ───────────────────────────────

@pytest.mark.asyncio
async def test_password_reset_marks_the_account_verified(client, db_session):
    """
    The user clicked a link sent to their address. That is the same proof the
    verification email asks for, so the reset must not drop them on /verify-email.
    """
    raw = generate_secure_token()
    user = make_user(
        "resetverif",
        password_reset_token_hash=hash_token(raw),
        password_reset_expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        email_verified=False,
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": "BrandNewPassword2026!"},
    )
    assert resp.status_code == 200

    await db_session.refresh(user)
    assert user.email_verified is True


@pytest.mark.asyncio
async def test_password_reset_discards_a_pending_verification_token(client, db_session):
    """The pending verification token is redundant once the account is verified."""
    reset_raw = generate_secure_token()
    verify_raw = generate_secure_token()
    user = make_user(
        "resetclears",
        password_reset_token_hash=hash_token(reset_raw),
        password_reset_expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        verification_token_hash=hash_token(verify_raw),
        verification_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        email_verified=False,
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_raw, "new_password": "BrandNewPassword2026!"},
    )
    assert resp.status_code == 200

    await db_session.refresh(user)
    assert user.email_verified is True
    assert user.verification_token_hash is None
    assert user.verification_token_expires_at is None

    # The stale verification token must no longer be usable.
    stale = await client.post("/api/v1/auth/verify-email", json={"token": verify_raw})
    assert stale.status_code == 400


@pytest.mark.asyncio
async def test_an_already_verified_account_stays_verified_after_reset(client, db_session):
    raw = generate_secure_token()
    user = make_user(
        "stayverif",
        password_reset_token_hash=hash_token(raw),
        password_reset_expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": "BrandNewPassword2026!"},
    )
    assert resp.status_code == 200
    await db_session.refresh(user)
    assert user.email_verified is True


# ─── Activation does not grant verification without real proof ────────────────

@pytest.mark.asyncio
async def test_activation_alone_does_not_verify_the_mailbox(db_session):
    """
    Activation authenticates with a bootstrap password handed out off-channel. That
    says nothing about who controls the mailbox, so it must not self-verify.
    """
    user = make_user("activate", password="TempPassword123!", must_change_password=True)
    db_session.add(user)
    await db_session.flush()

    service = AuthService(db_session)
    await service.activate_password(
        user=user,
        new_password="PersonalStrongPass2026!",
        current_password="TempPassword123!",
    )

    assert user.must_change_password is False
    assert user.email_verified is False, "a shared temporary password is not mailbox proof"


@pytest.mark.asyncio
async def test_activation_verifies_when_the_caller_proves_an_emailed_token(db_session):
    """The flag exists for a future flow that activates from an emailed link."""
    user = make_user(
        "activatetok",
        password="TempPassword123!",
        must_change_password=True,
        verification_token_hash=hash_token(generate_secure_token()),
        verification_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db_session.add(user)
    await db_session.flush()

    service = AuthService(db_session)
    await service.activate_password(
        user=user,
        new_password="PersonalStrongPass2026!",
        current_password="TempPassword123!",
        verified_via_email_token=True,
    )

    assert user.email_verified is True
    assert user.verification_token_hash is None


# ─── Login dispatches the code the verify page asks for ───────────────────────

@pytest.mark.asyncio
async def test_login_sends_exactly_one_verification_email_for_an_unverified_user(
    client, db_session
):
    """
    The incident: unverified users were bounced to /verify-email with no email ever
    sent. Login must dispatch it, and say so.
    """
    from app.core.email import clear_dev_mailbox, get_dev_mailbox

    clear_dev_mailbox()
    user = make_user("loginsend", password="CorrectHorse1!", email_verified=False)
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "CorrectHorse1!"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email_verified"] is False
    assert body["verification_sent"] is True

    sent = [m for m in get_dev_mailbox() if m["to"] == user.email]
    assert len(sent) == 1, "expected exactly one verification email"
    assert sent[0]["meta"]["action"] == "verify_email"

    await db_session.refresh(user)
    assert user.verification_token_hash is not None


@pytest.mark.asyncio
async def test_login_sends_nothing_for_an_already_verified_user(client, db_session):
    from app.core.email import clear_dev_mailbox, get_dev_mailbox

    clear_dev_mailbox()
    user = make_user("loginverified", password="CorrectHorse1!", email_verified=True)
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "CorrectHorse1!"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email_verified"] is True
    assert body["verification_sent"] is False
    assert [m for m in get_dev_mailbox() if m["to"] == user.email] == []


@pytest.mark.asyncio
async def test_a_second_login_inside_the_cooldown_does_not_send_again(client, db_session):
    """One email per cooldown window, however many times the user retries login."""
    from app.core.email import clear_dev_mailbox, get_dev_mailbox

    clear_dev_mailbox()
    user = make_user("logincooldown", password="CorrectHorse1!", email_verified=False)
    db_session.add(user)
    await db_session.flush()

    first = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "CorrectHorse1!"}
    )
    assert first.json()["verification_sent"] is True

    second = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "CorrectHorse1!"}
    )
    assert second.status_code == 200, "the login itself must still succeed"
    assert second.json()["verification_sent"] is False

    assert len([m for m in get_dev_mailbox() if m["to"] == user.email]) == 1


@pytest.mark.asyncio
async def test_login_does_not_resend_while_a_token_is_still_outstanding(client, db_session):
    """An unexpired token the user already has is not replaced on every login."""
    from app.core.email import clear_dev_mailbox, get_dev_mailbox

    clear_dev_mailbox()
    existing = hash_token(generate_secure_token())
    user = make_user(
        "loginpending",
        password="CorrectHorse1!",
        email_verified=False,
        verification_token_hash=existing,
        verification_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "CorrectHorse1!"}
    )
    assert resp.status_code == 200
    assert resp.json()["verification_sent"] is False
    assert [m for m in get_dev_mailbox() if m["to"] == user.email] == []

    await db_session.refresh(user)
    assert user.verification_token_hash == existing, "the outstanding token was replaced"


@pytest.mark.asyncio
async def test_login_still_succeeds_when_the_verification_email_fails(
    client, db_session, monkeypatch
):
    """
    A dead mail provider must not lock people out of the product. The login returns
    200 with verification_sent false, and no undelivered token is left behind.
    """
    from app.auth import service as service_module

    async def exploding_send(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(service_module, "send_verification_email", exploding_send)

    user = make_user("loginfail", password="CorrectHorse1!", email_verified=False)
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "CorrectHorse1!"}
    )
    assert resp.status_code == 200, "login must not fail because email failed"
    assert resp.json()["verification_sent"] is False

    await db_session.refresh(user)
    # A token staged for an email that never went out would both be unusable and
    # suppress every later attempt via the outstanding-token check.
    assert user.verification_token_hash is None
    assert user.verification_sent_at is None
