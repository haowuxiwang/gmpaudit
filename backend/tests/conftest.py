import os
import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Set test JWT key before app imports (startup event checks this)
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"

from app.core.database import Base, get_db
from app.core.auth import get_current_user, create_access_token
from app.main import app
from app.models.user import User

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(TEST_DATABASE_URL, echo=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        feishu_open_id="test_open_id_123",
        name="Test User",
        avatar_url="https://example.com/avatar.png",
        email="test@example.com",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def client(test_user: User) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        async with async_session() as session:
            yield session

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    # Create a valid JWT for the middleware
    token = create_access_token(data={"sub": test_user.feishu_open_id})

    async with AsyncClient(
        app=app,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
