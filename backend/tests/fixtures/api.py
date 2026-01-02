# -*- coding: utf-8 -*-
"""
API Fixtures

Provides fixtures for API testing including:
- Test FastAPI app
- Test HTTP client
- Authentication fixtures
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.app.main import create_app
from backend.db.models import Base
from backend.db.engine import get_session


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db_for_api():
    """Create test database for API tests."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest.fixture
async def test_app(test_db_for_api):
    """Create test FastAPI app."""
    app = create_app()
    
    # Override database dependency
    async_session = async_sessionmaker(
        test_db_for_api,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async def override_get_session():
        async with async_session() as session:
            yield session
    
    app.dependency_overrides[get_session] = override_get_session
    
    yield app
    
    app.dependency_overrides.clear()


@pytest.fixture
async def api_client(test_app):
    """Create test HTTP client."""
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_auth_token():
    """Create a mock authentication token."""
    return "mock-auth-token-12345"


@pytest.fixture
def authenticated_client(api_client, mock_auth_token):
    """Create an authenticated test client."""
    api_client.headers.update({"Authorization": f"Bearer {mock_auth_token}"})
    return api_client




