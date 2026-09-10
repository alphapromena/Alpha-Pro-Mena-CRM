"""
Transaction boundaries in the automatic migration runner, and the Alembic stamp.

Covers audit finding C4: the schema, the stamp and the team bootstrap shared one
transaction and one commit, so a failure in the bootstrap rolled the schema back with
it. That is how a missing BOOTSTRAP_PASSWORD became a schema outage.
"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core import auto_migrate
from app.core.auto_migrate import (
    AUTO_MIGRATE_REVISION,
    SUPERSEDED_REVISIONS,
    _run_migrations,
    _stamp_alembic_version,
)


@pytest.fixture
def db_file(tmp_path):
    """A file-backed SQLite database, so a commit has to survive a new session."""
    return tmp_path / "migrate_probe.sqlite3"


def _engine_for(db_file):
    return create_async_engine(f"sqlite+aiosqlite:///{db_file.as_posix()}")


# ─── The stamp helper ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "seed, expected",
    [
        (None, AUTO_MIGRATE_REVISION),                 # fresh database adopts the revision
        (SUPERSEDED_REVISIONS[0], AUTO_MIGRATE_REVISION),  # known-older stamp advances
        ("d9e0aa11bb22", "d9e0aa11bb22"),              # a newer revision is left alone
    ],
    ids=["fresh", "superseded", "ahead"],
)
async def test_stamp_never_moves_the_revision_backwards(db_file, seed, expected):
    """
    The stamp must never roll a database back. It previously inserted the head and
    then updated every other row to it, which both collided on the primary key and
    would have undone a later migration.
    """
    engine = _engine_for(db_file)
    async with AsyncSession(engine) as session:
        if seed is not None:
            await session.execute(text(
                "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
            ))
            await session.execute(
                text("INSERT INTO alembic_version VALUES (:v)"), {"v": seed}
            )
        await _stamp_alembic_version(session)
        rows = (await session.execute(text("SELECT version_num FROM alembic_version"))).scalars().all()

    await engine.dispose()
    assert rows == [expected]
    # Exactly one row: the old code could leave two, which Alembic treats as corrupt.
    assert len(rows) == 1


# ─── The transaction split ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_schema_stays_committed_when_the_bootstrap_fails(db_file, monkeypatch):
    """
    The regression test for C4. A bootstrap failure must leave the schema in place.
    """
    async def make_schema(session: AsyncSession) -> None:
        await session.execute(text("CREATE TABLE IF NOT EXISTS schema_marker (id INTEGER PRIMARY KEY)"))

    async def failing_bootstrap(session: AsyncSession) -> None:
        raise RuntimeError("BOOTSTRAP_PASSWORD env var is not set.")

    monkeypatch.setattr(auto_migrate, "_migrate_sqlite", make_schema)
    monkeypatch.setattr(auto_migrate, "_bootstrap_team_users", failing_bootstrap)

    engine = _engine_for(db_file)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        result = await _run_migrations(session)

    assert result["success"] is False
    assert result["phase"] == "bootstrap"
    assert result["schema_ok"] is True
    assert result["bootstrap_ok"] is False
    assert "BOOTSTRAP_PASSWORD" in result["error"]

    # The decisive check: a brand new session must still see the schema.
    async with Session() as verify:
        found = (await verify.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_marker'"
        ))).scalar_one_or_none()

    await engine.dispose()
    assert found == "schema_marker", "schema was rolled back by the bootstrap failure"


@pytest.mark.asyncio
async def test_bootstrap_failure_does_not_mark_migration_complete(db_file, monkeypatch):
    """A failed run must be retried on a later invocation, not latched as done."""
    async def make_schema(session: AsyncSession) -> None:
        await session.execute(text("CREATE TABLE IF NOT EXISTS schema_marker (id INTEGER PRIMARY KEY)"))

    async def failing_bootstrap(session: AsyncSession) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(auto_migrate, "_migrate_sqlite", make_schema)
    monkeypatch.setattr(auto_migrate, "_bootstrap_team_users", failing_bootstrap)
    monkeypatch.setattr(auto_migrate, "_migration_completed", False)

    engine = _engine_for(db_file)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        result = await _run_migrations(session)
    await engine.dispose()

    assert result["success"] is False
    assert auto_migrate._migration_completed is False


@pytest.mark.asyncio
async def test_schema_failure_reports_the_schema_phase(db_file, monkeypatch):
    """A schema failure is distinguishable from a bootstrap failure in the report."""
    async def failing_schema(session: AsyncSession) -> None:
        raise RuntimeError("relation does not exist")

    called = {"bootstrap": False}

    async def bootstrap(session: AsyncSession) -> None:
        called["bootstrap"] = True

    monkeypatch.setattr(auto_migrate, "_migrate_sqlite", failing_schema)
    monkeypatch.setattr(auto_migrate, "_bootstrap_team_users", bootstrap)

    engine = _engine_for(db_file)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        result = await _run_migrations(session)
    await engine.dispose()

    assert result["success"] is False
    assert result["phase"] == "schema"
    assert result["schema_ok"] is False
    # The bootstrap must not run against a schema that failed to apply.
    assert called["bootstrap"] is False


@pytest.mark.asyncio
async def test_both_phases_commit_on_the_happy_path(db_file, monkeypatch):
    async def make_schema(session: AsyncSession) -> None:
        await session.execute(text("CREATE TABLE IF NOT EXISTS schema_marker (id INTEGER PRIMARY KEY)"))

    async def bootstrap(session: AsyncSession) -> None:
        await session.execute(text("CREATE TABLE IF NOT EXISTS bootstrap_marker (id INTEGER PRIMARY KEY)"))

    monkeypatch.setattr(auto_migrate, "_migrate_sqlite", make_schema)
    monkeypatch.setattr(auto_migrate, "_bootstrap_team_users", bootstrap)

    engine = _engine_for(db_file)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        result = await _run_migrations(session)

    assert result["success"] is True
    assert result["schema_ok"] is True
    assert result["bootstrap_ok"] is True
    assert "schema_committed" in result["steps"]
    assert "bootstrap_committed" in result["steps"]

    async with Session() as verify:
        tables = (await verify.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_marker'"
        ))).scalars().all()

    await engine.dispose()
    assert set(tables) == {"schema_marker", "bootstrap_marker"}
