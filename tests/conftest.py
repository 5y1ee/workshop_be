"""테스트 공통 픽스처.

ASGI 앱을 직접 호출하는 httpx 클라이언트와, 로그인 테스트용 admin 시드를 제공한다.
실제 .env 의 DATABASE_URL(workshop_26) 에 붙는 E2E 테스트다.
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models.user import User

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin1234"
USER_USERNAME = "tester"
USER_PASSWORD = "tester1234"


async def _ensure_user(username: str, password: str, role: str) -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none() is None:
            db.add(
                User(
                    username=username,
                    password=hash_password(password),
                    nickname=username,
                    role=role,
                )
            )
            await db.commit()


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine():
    """테스트마다 엔진 커넥션 풀을 정리해 'Event loop is closed' 경고를 막는다.

    async 엔진은 테스트별 이벤트 루프에 묶이므로, 루프가 닫히기 전(픽스처 teardown)에
    같은 루프에서 dispose 해야 풀링된 커넥션이 깨끗하게 닫힌다.
    """
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def seeded_admin() -> dict[str, str]:
    """admin 유저가 없으면 생성한다 (재실행 안전)."""
    await _ensure_user(ADMIN_USERNAME, ADMIN_PASSWORD, "admin")
    return {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}


@pytest_asyncio.fixture
async def seeded_user() -> dict[str, str]:
    """일반(user) 권한 유저."""
    await _ensure_user(USER_USERNAME, USER_PASSWORD, "user")
    return {"username": USER_USERNAME, "password": USER_PASSWORD}


async def _login_token(client: AsyncClient, creds: dict[str, str]) -> str:
    res = await client.post("/api/auth/login", json=creds)
    return res.json()["access_token"]


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient, seeded_admin) -> dict[str, str]:
    token = await _login_token(client, seeded_admin)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user_headers(client: AsyncClient, seeded_user) -> dict[str, str]:
    token = await _login_token(client, seeded_user)
    return {"Authorization": f"Bearer {token}"}
