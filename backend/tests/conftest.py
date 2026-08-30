"""
Pytest configuration for backend testing.
Uses SQLite in-memory or async mock for fast, reliable unit & integration tests.
"""
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set test environment
os.environ["APP_ENV"] = "test"
os.environ["APP_SECRET_KEY"] = "test_app_secret_key_32_chars_long_123456"
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_32_chars_long_123456"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.database import Base, get_db
from app.main import create_app
from app.core.security import hash_password, create_access_token, normalize_email
from app.models.user import User, UserRole

# Test async engine
test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session
        await session.rollback()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def test_app(db_session):
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest_asyncio.fixture(scope="function")
async def client(test_app):
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def seed_test_users(db_session):
    admin = User(
        email="admin@test.com",
        normalized_email=normalize_email("admin@test.com"),
        first_name="Admin",
        last_name="User",
        password_hash=hash_password("Admin123!"),
        role=UserRole.ADMIN,
    )
    sales = User(
        email="sales@test.com",
        normalized_email=normalize_email("sales@test.com"),
        first_name="Sales",
        last_name="User",
        password_hash=hash_password("Sales123!"),
        role=UserRole.SALES_USER,
    )
    db_session.add_all([admin, sales])
    await db_session.flush()
    return {"admin": admin, "sales": sales}
