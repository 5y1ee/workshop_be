"""포켓몬 UI 화면용 조회 엔드포인트 테스트.

- GET /seasons/{id}/scoreboard  (시즌 누적 팀 점수)
- GET /teams/{id}/members        (팀원, 로그인 유저 누구나)
- GET /rewards                   (리워드 도감)
"""

import uuid

from app.db.session import AsyncSessionLocal
from app.models.reward import Reward


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _season_with_two_teams(client, admin_headers):
    season_id = (
        await client.post(
            "/api/seasons", json={"name": _unique("시즌")}, headers=admin_headers
        )
    ).json()["id"]
    red = (
        await client.post(
            f"/api/seasons/{season_id}/teams", json={"name": "레드팀"}, headers=admin_headers
        )
    ).json()["id"]
    blue = (
        await client.post(
            f"/api/seasons/{season_id}/teams", json={"name": "블루팀"}, headers=admin_headers
        )
    ).json()["id"]
    return season_id, red, blue


async def _session_for_season(client, admin_headers, season_id):
    game_id = (
        await client.post(
            "/api/games",
            json={"title": _unique("게임"), "participant_type": "team_vs", "input_type": "button"},
            headers=admin_headers,
        )
    ).json()["id"]
    timetable_id = (
        await client.post(
            f"/api/seasons/{season_id}/timetable",
            json={"game_id": game_id, "order_index": 1},
            headers=admin_headers,
        )
    ).json()["id"]
    return (
        await client.post(f"/api/timetable/{timetable_id}/session", headers=admin_headers)
    ).json()["id"]


# ----- 시즌 스코어보드 -----

async def test_season_scoreboard_aggregates_and_sorts(client, admin_headers):
    season_id, red, blue = await _season_with_two_teams(client, admin_headers)
    session_id = await _session_for_season(client, admin_headers, season_id)

    for sc in (10, 25):  # red = 35
        await client.post(
            f"/api/sessions/{session_id}/scores",
            json={"subject_type": "team", "subject_id": red, "score": sc},
            headers=admin_headers,
        )
    await client.post(  # blue = 15
        f"/api/sessions/{session_id}/scores",
        json={"subject_type": "team", "subject_id": blue, "score": 15},
        headers=admin_headers,
    )

    res = await client.get(f"/api/seasons/{season_id}/scoreboard", headers=admin_headers)
    assert res.status_code == 200
    board = res.json()
    # 두 팀 모두 포함, 내림차순
    assert board[0] == {"team_id": red, "name": "레드팀", "total_score": 35}
    assert board[1] == {"team_id": blue, "name": "블루팀", "total_score": 15}


async def test_season_scoreboard_includes_zero_teams(client, admin_headers):
    season_id, red, blue = await _season_with_two_teams(client, admin_headers)
    # 점수 기록 전 — 두 팀 모두 0점으로 노출돼야 한다
    res = await client.get(f"/api/seasons/{season_id}/scoreboard", headers=admin_headers)
    assert res.status_code == 200
    board = res.json()
    assert {b["team_id"] for b in board} == {red, blue}
    assert all(b["total_score"] == 0 for b in board)


async def test_scoreboard_visible_to_normal_user(client, admin_headers, user_headers):
    season_id, _, _ = await _season_with_two_teams(client, admin_headers)
    res = await client.get(f"/api/seasons/{season_id}/scoreboard", headers=user_headers)
    assert res.status_code == 200


# ----- 팀원 -----

async def test_team_members_returns_assigned_users(client, admin_headers):
    season_id, red, _ = await _season_with_two_teams(client, admin_headers)
    user_id = (
        await client.post(
            "/api/users",
            json={
                "username": _unique("p"),
                "password": "pw12345678",
                "nickname": "홍길동",
                "role": "user",
                "team_id": red,
            },
            headers=admin_headers,
        )
    ).json()["id"]

    res = await client.get(f"/api/teams/{red}/members", headers=admin_headers)
    assert res.status_code == 200
    members = res.json()
    assert any(m["id"] == user_id and m["nickname"] == "홍길동" for m in members)


async def test_team_members_visible_to_normal_user(client, admin_headers, user_headers):
    season_id, red, _ = await _season_with_two_teams(client, admin_headers)
    res = await client.get(f"/api/teams/{red}/members", headers=user_headers)
    assert res.status_code == 200


async def test_team_members_unknown_team_404(client, admin_headers):
    res = await client.get("/api/teams/99999999/members", headers=admin_headers)
    assert res.status_code == 404


# ----- 리워드 도감 -----

async def test_rewards_list(client, admin_headers):
    async with AsyncSessionLocal() as db:
        reward = Reward(name=_unique("상품권"), description="테스트 보상", total_count=3)
        db.add(reward)
        await db.commit()
        await db.refresh(reward)
        reward_id = reward.id

    res = await client.get("/api/rewards", headers=admin_headers)
    assert res.status_code == 200
    rewards = res.json()
    assert any(r["id"] == reward_id and r["total_count"] == 3 for r in rewards)


async def test_rewards_requires_auth(client):
    res = await client.get("/api/rewards")
    assert res.status_code == 401
