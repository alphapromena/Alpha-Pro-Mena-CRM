"""
Database configuration — async SQLAlchemy engine + session factory.

Supports:
  * SQLite (local dev / tests) with foreign keys enforced on every connection
  * PostgreSQL via asyncpg, including transaction-mode poolers (Supabase Supavisor,
    Neon/PgBouncer) where prepared statements must be disabled.
"""
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()


def _prepared_statement_name() -> str:
    return "__asyncpg_" + uuid.uuid4().hex + "__"


def _build_engine():
    url = settings.database_url
    kwargs: dict = {"echo": settings.app_debug}
    connect_args: dict = {}

    if url.startswith("sqlite"):
        pass
    elif settings.database_pooled:
        # An external pooler already multiplexes connections; don't stack a second pool
        # on top of it, and never rely on named prepared statements surviving a transaction.
        kwargs["poolclass"] = NullPool
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_name_func"] = _prepared_statement_name
    else:
        kwargs["pool_size"] = settings.database_pool_size
        kwargs["max_overflow"] = settings.database_max_overflow
        kwargs["pool_pre_ping"] = True
        kwargs["pool_recycle"] = 300

    if connect_args:
        kwargs["connect_args"] = connect_args

    eng = create_async_engine(url, **kwargs)

    if url.startswith("sqlite"):
        @event.listens_for(eng.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return eng


engine = _build_engine()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for use outside request context (jobs, scripts)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
