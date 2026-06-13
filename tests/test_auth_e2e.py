"""인증 플로우 E2E 테스트: login → /me, 그리고 실패 케이스."""


async def test_health(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


async def test_login_returns_token(client, seeded_admin):
    res = await client.post("/api/auth/login", json=seeded_admin)
    assert res.status_code == 200
    data = res.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["role"] == "admin"


async def test_me_with_token(client, seeded_admin):
    login = await client.post("/api/auth/login", json=seeded_admin)
    token = login.json()["access_token"]

    res = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert res.json()["username"] == seeded_admin["username"]
    assert res.json()["role"] == "admin"


async def test_login_wrong_password(client, seeded_admin):
    res = await client.post(
        "/api/auth/login",
        json={"username": seeded_admin["username"], "password": "wrong-password"},
    )
    assert res.status_code == 401


async def test_me_requires_auth(client):
    res = await client.get("/api/auth/me")
    assert res.status_code == 401
