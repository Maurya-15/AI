"""Pytest configuration and fixtures."""

import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import Settings
from app.db import Base, get_db
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings():
    """Create test settings."""
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost:5432/test_devsync_sales",
        email_from="test@example.com",
        business_address="Test Address",
        sendgrid_api_key="test_key",
        abstractapi_key="test_key",
        numverify_key="test_key",
        openai_api_key="test_key",
        dry_run_mode=True,
        approval_mode=True,
        daily_email_cap=10,
        daily_call_cap=10
    )


@pytest.fixture(scope="function")
async def test_db(test_settings) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    engine = create_async_engine(
        str(test_settings.database_url),
        poolclass=NullPool,
        echo=False
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
def override_get_db(test_db):
    """Override get_db dependency."""
    async def _override_get_db():
        yield test_db
    
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()
