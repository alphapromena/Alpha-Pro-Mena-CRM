"""
Token lifecycle for email verification and password reset, plus the lockout
regression from audit finding C2.

The lockout tests deliberately do not use the shared `client` fixture. That fixture
overrides get_db with a bare yield, which does not commit or roll back, so it cannot
reproduce the interaction that broke lockout in production. These build their own app
against a file-backed database with the real get_db semantics.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.core.security import generate_secure_token, hash_password, hash_token, normalize_email
from app.main import create_app
from app.models.user import User, UserRole


def _user(email_prefix="tok", password="OldPassword123!", **kwargs) -> User:
    email = f"{email_prefix}_{uuid.uuid4().hex[:6]}@alphapromena.com"
    defaults = dict(
        email=email,
        normalized_email=normalize_email(email),
        first_name="Token",
        last_name="Tester",
        password_hash=hash_password(password),
        role=UserRole.SALES_USER,
        is_active=True,
        is_locked=False,
        login_attempts=0,
        email_verified=False,
    )
    defaults.update(kwargs)
    return User(**defaults)


# ─── Email verification ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_email_happy_path_stores_only_the_hash(client, db_session):
    raw = generate_secure_token()
    user = _user(
        "verify",
        verification_token_hash=hash_token(raw),
        verification_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db_session.add(user)
    await db_session.flush()

    # The raw token is never persisted; only its hash is.
    assert user.verification_token_hash != raw

    resp = await client.post("/api/v1/auth/verify-email", json={"token": raw})
    assert resp.status_code == 200
    assert resp.json()["email_verified"] is True

    await db_session.refresh(user)
    assert user.email_verified is True
    # One-time use: the stored hash is cleared on success.
    assert user.verification_token_hash is None
    assert user.verification_token_expires_at is None


@pytest.mark.asyncio
async def test_verify_email_rejects_an_expired_token(client, db_session):
    raw = generate_secure_token()
    user = _user(
        "expired",
        verification_token_hash=hash_token(raw),
        verification_token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.post("/api/v1/auth/verify-email", json={"token": raw})
    assert resp.status_code == 400
    assert "expired" in resp.json()["error"]["message"].lower()

    await db_session.refresh(user)
    assert user.email_verified is False


@pytest.mark.asyncio
async def test_verify_email_rejects_a_reused_token(client, db_session):
    raw = generate_secure_token()
    user = _user(
        "reuse",
        verification_token_hash=hash_token(raw),
        verification_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db_session.add(user)
    await db_session.flush()

    first = await client.post("/api/v1/auth/verify-email", json={"token": raw})
    assert first.status_code == 200

    second = await client.post("/api/v1/auth/verify-email", json={"token": raw})
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_rejects_a_token_belonging_to_another_address(client, db_session):
    raw = generate_secure_token()
    owner = _user(
        "owner",
        verification_token_hash=hash_token(raw),
        verification_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    other = _user("other")
    db_session.add_all([owner, other])
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/verify-email", json={"token": raw, "email": other.email}
    )
    assert resp.status_code == 400


# ─── Password reset ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reset_password_happy_path_clears_the_token_and_unlocks(client, db_session):
    raw = generate_secure_token()
    user = _user(
        "reset",
        password="OldPassword123!",
        password_reset_token_hash=hash_token(raw),
        password_reset_expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        is_locked=True,
        login_attempts=5,
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": "BrandNewPassword2026!"},
    )
    assert resp.status_code == 200

    await db_session.refresh(user)
    assert user.password_reset_token_hash is None
    assert user.password_reset_expires_at is None
    assert user.must_change_password is False
    # A successful reset is also the documented way out of a lockout.
    assert user.is_locked is False
    assert user.login_attempts == 0

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "BrandNewPassword2026!"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_rejects_an_expired_token(client, db_session):
    raw = generate_secure_token()
    user = _user(
        "resetexp",
        password_reset_token_hash=hash_token(raw),
        password_reset_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(user)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": "BrandNewPassword2026!"},
    )
    assert resp.status_code == 400
    assert "expired" in resp.json()["error"]["message"].lower()

    # The old password still works, so nothing was changed.
    login = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "OldPassword123!"}
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_rejects_a_reused_token(client, db_session):
    raw = generate_secure_token()
    user = _user(
        "resetreuse",
        password_reset_token_hash=hash_token(raw),
        password_reset_expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    db_session.add(user)
    await db_session.flush()

    first = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": "BrandNewPassword2026!"},
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": "AnotherPassword2026!"},
    )
    assert second.status_code == 400


# ─── Logout works without a live session ──────────────────────────────────────

@pytest.mark.asyncio
async def test_logout_succeeds_without_any_session(client):
    """
    Logout used to require a valid access token, so an expired session could never
    clear its own cookies.
    """
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_logout_clears_the_session_hint_cookie(client, db_session):
    user = _user("logout", email_verified=True)
    db_session.add(user)
    await db_session.flush()

    login = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "OldPassword123!"}
    )
    assert login.status_code == 200
    # The hint is readable by the SPA so an anonymous load makes no auth calls.
    assert "session_active" in login.headers.get("set-cookie", "")

    out = await client.post("/api/v1/auth/logout")
    assert out.status_code == 200
    cleared = out.headers.get("set-cookie", "")
    assert "session_active" in cleared


# ─── Account lockout, with real transaction semantics ─────────────────────────

@pytest_asyncio.fixture
async def real_db_client(tmp_path):
    """
    An app wired to a file-backed database through the real get_db semantics:
    commit when the request succeeds, roll back when it raises.

    This is what makes the lockout regression observable. The shared fixture's bare
    yield never rolls back, so it would pass even with the bug present.
    """
    db_file = tmp_path / "lockout.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file.as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, Session

    await engine.dispose()


@pytest.mark.asyncio
async def test_failed_logins_persist_and_lock_the_account(real_db_client):
    """
    Audit finding C2. The attempt counter was written with flush() and the 401 that
    followed rolled it back, so the account never locked and brute-force protection
    did not exist.
    """
    client, Session = real_db_client

    async with Session() as s:
        user = _user("lockme", password="CorrectHorse1!", email_verified=True)
        s.add(user)
        await s.commit()
        email = user.email

    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "WrongPassword9!"}
        )
        assert resp.status_code == 401

    async with Session() as s:
        stored = (await s.execute(
            select(User).where(User.normalized_email == normalize_email(email))
        )).scalar_one()
        assert stored.login_attempts == 5, "the attempt counter was rolled back"
        assert stored.is_locked is True
        assert stored.locked_until is not None

    # Locked accounts are refused even with the correct password.
    locked = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "CorrectHorse1!"}
    )
    assert locked.status_code == 423


@pytest.mark.asyncio
async def test_a_locked_account_answers_the_same_for_right_and_wrong_passwords(real_db_client):
    """
    The lockout check used to run after the password check, so a locked account
    answered 401 for a wrong password and 423 for the right one. That let an attacker
    confirm a correct guess against an account they had already locked.
    """
    client, Session = real_db_client

    async with Session() as s:
        user = _user(
            "oracle",
            password="CorrectHorse1!",
            email_verified=True,
            is_locked=True,
            login_attempts=5,
            locked_until=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        s.add(user)
        await s.commit()
        email = user.email

    wrong = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "WrongPassword9!"}
    )
    right = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "CorrectHorse1!"}
    )

    assert wrong.status_code == right.status_code == 423
    assert wrong.json()["error"]["code"] == right.json()["error"]["code"]


@pytest.mark.asyncio
async def test_a_successful_login_resets_the_attempt_counter(real_db_client):
    client, Session = real_db_client

    async with Session() as s:
        user = _user("resetcount", password="CorrectHorse1!", email_verified=True)
        s.add(user)
        await s.commit()
        email = user.email

    for _ in range(3):
        await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "WrongPassword9!"}
        )

    ok = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "CorrectHorse1!"}
    )
    assert ok.status_code == 200

    async with Session() as s:
        stored = (await s.execute(
            select(User).where(User.normalized_email == normalize_email(email))
        )).scalar_one()
        assert stored.login_attempts == 0
        assert stored.is_locked is False
        assert stored.last_login_at is not None
