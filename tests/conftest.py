import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.session import engine
from app.main import app


@pytest.fixture(autouse=True)
async def clean_db():
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE subscriptions, payments, users RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def user_id() -> int:
    async with engine.begin() as conn:
        result = await conn.execute(
            text("INSERT INTO users (email) VALUES ('user@example.com') RETURNING id")
        )
        return result.scalar_one()
