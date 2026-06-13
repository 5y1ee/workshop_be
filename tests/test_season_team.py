"""Season / Team 관리 API 테스트."""

import uuid


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def test_season_crud_flow(client, admin_headers):
    # 생성
    name = _unique("시즌")
    res = await client.post("/api/seasons", json={"name": name}, headers=admin_headers)
    assert res.status_code == 201
    season = res.json()
    assert season["name"] == name
    assert season["status"] == "preparing"
    assert season["started_at"] is None
    season_id = season["id"]

    # 단건 조회
    res = await client.get(f"/api/seasons/{season_id}", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["id"] == season_id

    # 목록에 포함
    res = await client.get("/api/seasons", headers=admin_headers)
    assert res.status_code == 200
    assert any(s["id"] == season_id for s in res.json())

    # 상태 active 로 변경 -> started_at 자동 기록
    res = await client.patch(
        f"/api/seasons/{season_id}", json={"status": "active"}, headers=admin_headers
    )
    assert res.status_code == 200
    updated = res.json()
    assert updated["status"] == "active"
    assert updated["started_at"] is not None
    assert updated["updated_at"] is not None

    # 상태 done 으로 변경 -> ended_at 자동 기록
    res = await client.patch(
        f"/api/seasons/{season_id}", json={"status": "done"}, headers=admin_headers
    )
    assert res.json()["ended_at"] is not None


async def test_season_get_404(client, admin_headers):
    res = await client.get("/api/seasons/99999999", headers=admin_headers)
    assert res.status_code == 404


async def test_season_invalid_status_rejected(client, admin_headers):
    res = await client.post("/api/seasons", json={"name": _unique("s")}, headers=admin_headers)
    season_id = res.json()["id"]
    res = await client.patch(
        f"/api/seasons/{season_id}", json={"status": "bogus"}, headers=admin_headers
    )
    assert res.status_code == 422  # Literal 검증 실패


async def test_season_create_requires_admin(client, user_headers):
    res = await client.post("/api/seasons", json={"name": "x"}, headers=user_headers)
    assert res.status_code == 403


async def test_team_crud_flow(client, admin_headers):
    # 시즌 먼저 생성
    res = await client.post("/api/seasons", json={"name": _unique("시즌")}, headers=admin_headers)
    season_id = res.json()["id"]

    # 팀 생성
    res = await client.post(
        f"/api/seasons/{season_id}/teams", json={"name": "레드팀"}, headers=admin_headers
    )
    assert res.status_code == 201
    team = res.json()
    assert team["name"] == "레드팀"
    assert team["season_id"] == season_id
    team_id = team["id"]

    # 시즌별 목록
    res = await client.get(f"/api/seasons/{season_id}/teams", headers=admin_headers)
    assert res.status_code == 200
    assert [t["id"] for t in res.json()] == [team_id]

    # 단건
    res = await client.get(f"/api/teams/{team_id}", headers=admin_headers)
    assert res.status_code == 200

    # 이름 변경
    res = await client.patch(
        f"/api/teams/{team_id}", json={"name": "블루팀"}, headers=admin_headers
    )
    assert res.status_code == 200
    assert res.json()["name"] == "블루팀"


async def test_team_create_unknown_season_404(client, admin_headers):
    res = await client.post(
        "/api/seasons/99999999/teams", json={"name": "x"}, headers=admin_headers
    )
    assert res.status_code == 404


async def test_team_create_requires_admin(client, user_headers, admin_headers):
    res = await client.post("/api/seasons", json={"name": _unique("시즌")}, headers=admin_headers)
    season_id = res.json()["id"]
    res = await client.post(
        f"/api/seasons/{season_id}/teams", json={"name": "x"}, headers=user_headers
    )
    assert res.status_code == 403
