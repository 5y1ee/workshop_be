"""포켓몬 UI 화면용 조회/관리 엔드포인트 테스트.

- GET  /seasons/{id}/scoreboard            (시즌 누적 팀 점수)
- GET  /teams/{id}/members                  (팀원 = 멤버십 조인)
- POST /seasons/{id}/teams/{tid}/members    (유저 배치)
- GET  /seasons/{id}/my-team                (내 팀)
- GET/POST /seasons/{id}/rewards            (시즌별 리워드 도감)
"""

import uuid


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _season_with_two_teams(client, admin_headers):
    season_id = (
        await client.post(
            "/api/seasons", json={"name": _unique("시즌")}, headers=admin_headers
        )
    ).json()["id"]
    red_id = (
        await client.post(
            f"/api/seasons/{season_id}/teams", json={"name": "레드팀"}, headers=admin_headers
        )
    ).json()["id"]
    blue_id = (
        await client.post(
            f"/api/seasons/{season_id}/teams", json={"name": "블루팀"}, headers=admin_headers
        )
    ).json()["id"]
    return season_id, red_id, blue_id


async def _create_user(client, admin_headers, nickname="참가자"):
    return (
        await client.post(
            "/api/users",
            json={
                "username": _unique("p"),
                "password": "pw12345678",
                "nickname": nickname,
                "role": "user",
            },
            headers=admin_headers,
        )
    ).json()["id"]


async def _create_login_user(client, admin_headers, nickname="참가자"):
    username = _unique("p")
    password = "pw12345678"
    user_id = (
        await client.post(
            "/api/users",
            json={
                "username": username,
                "password": password,
                "nickname": nickname,
                "role": "user",
            },
            headers=admin_headers,
        )
    ).json()["id"]
    login = await client.post(
        "/api/auth/login", data={"username": username, "password": password}
    )
    return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _session_for_season(
    client, admin_headers, season_id, participant_type="team_vs", order_index=1
):
    game_id = (
        await client.post(
            "/api/games",
            json={
                "title": _unique("게임"),
                "participant_type": participant_type,
                "input_type": "button",
            },
            headers=admin_headers,
        )
    ).json()["id"]
    timetable_id = (
        await client.post(
            f"/api/seasons/{season_id}/timetable",
            json={"game_id": game_id, "order_index": order_index},
            headers=admin_headers,
        )
    ).json()["id"]
    session_id = (
        await client.post(f"/api/timetable/{timetable_id}/session", headers=admin_headers)
    ).json()["id"]
    # 점수 기록이 가능하도록 in_progress 까지 전이
    for to in ("ready", "in_progress"):
        await client.post(
            f"/api/sessions/{session_id}/transition",
            json={"to": to},
            headers=admin_headers,
        )
    return session_id


# ----- 시즌 스코어보드 -----

async def test_season_scoreboard_aggregates_and_sorts(client, admin_headers):
    season_id, red_id, blue_id = await _season_with_two_teams(client, admin_headers)
    session_id = await _session_for_season(client, admin_headers, season_id)

    for sc in (10, 25):  # red = 35
        await client.post(
            f"/api/sessions/{session_id}/scores",
            json={"subject_type": "team", "subject_id": red_id, "score": sc},
            headers=admin_headers,
        )
    await client.post(  # blue = 15
        f"/api/sessions/{session_id}/scores",
        json={"subject_type": "team", "subject_id": blue_id, "score": 15},
        headers=admin_headers,
    )

    res = await client.get(f"/api/seasons/{season_id}/scoreboard", headers=admin_headers)
    assert res.status_code == 200
    board = res.json()
    # 두 팀 모두 포함, 내림차순
    assert board[0] == {"team_id": red_id, "name": "레드팀", "total_score": 35}
    assert board[1] == {"team_id": blue_id, "name": "블루팀", "total_score": 15}


async def test_season_scoreboard_includes_zero_teams(client, admin_headers):
    season_id, red_id, blue_id = await _season_with_two_teams(client, admin_headers)
    # 점수 기록 전 — 두 팀 모두 0점으로 노출돼야 한다
    res = await client.get(f"/api/seasons/{season_id}/scoreboard", headers=admin_headers)
    assert res.status_code == 200
    board = res.json()
    assert {b["team_id"] for b in board} == {red_id, blue_id}
    assert all(b["total_score"] == 0 for b in board)


async def test_scoreboard_visible_to_normal_user(client, admin_headers, user_headers):
    season_id, _, _ = await _season_with_two_teams(client, admin_headers)
    res = await client.get(f"/api/seasons/{season_id}/scoreboard", headers=user_headers)
    assert res.status_code == 200


async def test_season_user_scoreboard_aggregates_and_sorts(client, admin_headers):
    season_id, red_id, blue_id = await _season_with_two_teams(client, admin_headers)
    user_a = await _create_user(client, admin_headers, nickname="개인A")
    user_b = await _create_user(client, admin_headers, nickname="개인B")
    await client.post(
        f"/api/seasons/{season_id}/teams/{red_id}/members",
        json={"user_id": user_a},
        headers=admin_headers,
    )
    await client.post(
        f"/api/seasons/{season_id}/teams/{blue_id}/members",
        json={"user_id": user_b},
        headers=admin_headers,
    )
    session_id = await _session_for_season(client, admin_headers, season_id)

    for sc in (7, 8):
        await client.post(
            f"/api/sessions/{session_id}/scores",
            json={"subject_type": "user", "subject_id": user_a, "score": sc},
            headers=admin_headers,
        )

    res = await client.get(f"/api/seasons/{season_id}/user-scoreboard", headers=admin_headers)
    assert res.status_code == 200
    board = res.json()
    assert board[0] == {"user_id": user_a, "name": "개인A", "total_score": 15}
    assert board[1] == {"user_id": user_b, "name": "개인B", "total_score": 0}


async def test_gacha_cost_spends_user_point_without_changing_cumulative_score(
    client, admin_headers
):
    season_id, red_id, _ = await _season_with_two_teams(client, admin_headers)
    user_id, auth_headers = await _create_login_user(client, admin_headers, nickname="뽑기러")
    await client.post(
        f"/api/seasons/{season_id}/teams/{red_id}/members",
        json={"user_id": user_id},
        headers=admin_headers,
    )
    session_id = await _session_for_season(client, admin_headers, season_id)
    await client.post(
        f"/api/sessions/{session_id}/scores",
        json={"subject_type": "user", "subject_id": user_id, "score": 10},
        headers=admin_headers,
    )
    await client.patch(
        f"/api/seasons/{season_id}",
        json={"gacha_pull_cost": 3},
        headers=admin_headers,
    )

    res = await client.post(f"/api/gacha/pull?season_id={season_id}", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["pull_cost"] == 3
    assert body["remaining_point"] == 7

    board = (
        await client.get(f"/api/seasons/{season_id}/user-scoreboard", headers=admin_headers)
    ).json()
    assert next(row for row in board if row["user_id"] == user_id)["total_score"] == 10
    me = (await client.get("/api/auth/me", headers=auth_headers)).json()
    assert me["point"] == 7

    await client.patch(
        f"/api/seasons/{season_id}",
        json={"gacha_pull_cost": 8},
        headers=admin_headers,
    )
    res = await client.post(f"/api/gacha/pull?season_id={season_id}", headers=auth_headers)
    assert res.status_code == 402


async def test_user_status_includes_admins_users_scores_and_points(client, admin_headers):
    season_id, red_id, _ = await _season_with_two_teams(client, admin_headers)
    user_id = await _create_user(client, admin_headers, nickname="현황유저")
    await client.post(
        f"/api/seasons/{season_id}/teams/{red_id}/members",
        json={"user_id": user_id},
        headers=admin_headers,
    )
    session_id = await _session_for_season(client, admin_headers, season_id)
    await client.post(
        f"/api/sessions/{session_id}/scores",
        json={"subject_type": "user", "subject_id": user_id, "score": 6},
        headers=admin_headers,
    )

    res = await client.get(f"/api/seasons/{season_id}/user-status", headers=admin_headers)
    assert res.status_code == 200
    rows = res.json()
    assert any(row["role"] == "admin" for row in rows)
    user_row = next(row for row in rows if row["user_id"] == user_id)
    assert user_row["team_id"] == red_id
    assert user_row["team_name"] == "레드팀"
    assert user_row["cumulative_score"] == 6
    assert user_row["point"] == 6

    res = await client.get(f"/api/seasons/{season_id}/user-status")
    assert res.status_code == 401


async def test_team_scoreboard_rolls_member_individual_scores(client, admin_headers):
    # 팀 대항전(team_vs): 팀 직접 점수 + 멤버 개인 점수가 모두 팀 총점에 합산된다.
    season_id, red_id, blue_id = await _season_with_two_teams(client, admin_headers)
    user_a = await _create_user(client, admin_headers, nickname="개인A")
    await client.post(
        f"/api/seasons/{season_id}/teams/{red_id}/members",
        json={"user_id": user_a},
        headers=admin_headers,
    )
    session_id = await _session_for_season(client, admin_headers, season_id)

    # 레드팀 직접 6점 + 레드팀 소속 개인 4점 → 레드팀 10점
    await client.post(
        f"/api/sessions/{session_id}/scores",
        json={"subject_type": "team", "subject_id": red_id, "score": 6},
        headers=admin_headers,
    )
    await client.post(
        f"/api/sessions/{session_id}/scores",
        json={"subject_type": "user", "subject_id": user_a, "score": 4},
        headers=admin_headers,
    )

    res = await client.get(f"/api/seasons/{season_id}/scoreboard", headers=admin_headers)
    board = {b["team_id"]: b["total_score"] for b in res.json()}
    assert board[red_id] == 10
    assert board[blue_id] == 0


async def test_individual_game_scores_excluded_from_team_scoreboard(client, admin_headers):
    # 개인전(individual): 개인 점수는 팀 총점에 합산되지 않고 개인 랭킹에만 반영된다.
    season_id, red_id, blue_id = await _season_with_two_teams(client, admin_headers)
    user_a = await _create_user(client, admin_headers, nickname="개인A")
    await client.post(
        f"/api/seasons/{season_id}/teams/{red_id}/members",
        json={"user_id": user_a},
        headers=admin_headers,
    )
    session_id = await _session_for_season(
        client, admin_headers, season_id, participant_type="individual"
    )
    await client.post(
        f"/api/sessions/{session_id}/scores",
        json={"subject_type": "user", "subject_id": user_a, "score": 9},
        headers=admin_headers,
    )

    # 팀 스코어보드에는 반영되지 않음
    team_board = {
        b["team_id"]: b["total_score"]
        for b in (
            await client.get(f"/api/seasons/{season_id}/scoreboard", headers=admin_headers)
        ).json()
    }
    assert team_board[red_id] == 0
    assert team_board[blue_id] == 0

    # 개인 스코어보드에는 반영됨
    user_board = {
        b["user_id"]: b["total_score"]
        for b in (
            await client.get(
                f"/api/seasons/{season_id}/user-scoreboard", headers=admin_headers
            )
        ).json()
    }
    assert user_board[user_a] == 9


# ----- 팀원 / 멤버십 -----

async def test_team_members_returns_assigned_users(client, admin_headers):
    season_id, red_id, _ = await _season_with_two_teams(client, admin_headers)
    user_id = await _create_user(client, admin_headers, nickname="홍길동")
    # 멤버십으로 배정
    res = await client.post(
        f"/api/seasons/{season_id}/teams/{red_id}/members",
        json={"user_id": user_id},
        headers=admin_headers,
    )
    assert res.status_code == 201

    res = await client.get(f"/api/teams/{red_id}/members", headers=admin_headers)
    assert res.status_code == 200
    members = res.json()
    assert any(m["id"] == user_id and m["nickname"] == "홍길동" for m in members)


async def test_reassign_moves_user_between_teams(client, admin_headers):
    """같은 시즌에서 재배정하면 기존 팀 멤버십은 교체된다."""
    season_id, red_id, blue_id = await _season_with_two_teams(client, admin_headers)
    user_id = await _create_user(client, admin_headers)

    await client.post(
        f"/api/seasons/{season_id}/teams/{red_id}/members",
        json={"user_id": user_id},
        headers=admin_headers,
    )
    await client.post(
        f"/api/seasons/{season_id}/teams/{blue_id}/members",
        json={"user_id": user_id},
        headers=admin_headers,
    )

    red_members = (
        await client.get(f"/api/teams/{red_id}/members", headers=admin_headers)
    ).json()
    blue_members = (
        await client.get(f"/api/teams/{blue_id}/members", headers=admin_headers)
    ).json()
    assert all(m["id"] != user_id for m in red_members)
    assert any(m["id"] == user_id for m in blue_members)


async def test_my_team_reflects_active_season_membership(client, admin_headers):
    """활성 시즌에 배정되면 로그인 응답 team_id 와 my-team 이 반영된다."""
    season_id, red_id, _ = await _season_with_two_teams(client, admin_headers)
    await client.patch(
        f"/api/seasons/{season_id}", json={"status": "active"}, headers=admin_headers
    )
    username = _unique("p")
    user_id = (
        await client.post(
            "/api/users",
            json={
                "username": username,
                "password": "pw12345678",
                "nickname": "트레이너",
                "role": "user",
            },
            headers=admin_headers,
        )
    ).json()["id"]
    await client.post(
        f"/api/seasons/{season_id}/teams/{red_id}/members",
        json={"user_id": user_id},
        headers=admin_headers,
    )

    login = await client.post(
        "/api/auth/login", data={"username": username, "password": "pw12345678"}
    )
    assert login.json()["team_id"] == red_id
    token = login.json()["access_token"]

    mine = await client.get(
        f"/api/seasons/{season_id}/my-team",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert mine.json()["team_id"] == red_id


async def test_team_members_visible_to_normal_user(client, admin_headers, user_headers):
    season_id, red_id, _ = await _season_with_two_teams(client, admin_headers)
    res = await client.get(f"/api/teams/{red_id}/members", headers=user_headers)
    assert res.status_code == 200


async def test_team_members_unknown_team_404(client, admin_headers):
    res = await client.get("/api/teams/99999999/members", headers=admin_headers)
    assert res.status_code == 404


# ----- 소프트 삭제 -----

async def test_soft_deleted_team_hidden_from_list(client, admin_headers):
    season_id, red_id, blue_id = await _season_with_two_teams(client, admin_headers)
    res = await client.delete(f"/api/teams/{red_id}", headers=admin_headers)
    assert res.status_code == 204

    teams = (
        await client.get(f"/api/seasons/{season_id}/teams", headers=admin_headers)
    ).json()
    ids = {t["id"] for t in teams}
    assert red_id not in ids
    assert blue_id in ids


async def test_soft_deleted_season_hidden_from_list(client, admin_headers):
    season_id, _, _ = await _season_with_two_teams(client, admin_headers)
    res = await client.delete(f"/api/seasons/{season_id}", headers=admin_headers)
    assert res.status_code == 204

    seasons = (await client.get("/api/seasons", headers=admin_headers)).json()
    assert all(s["id"] != season_id for s in seasons)


# ----- 리워드 도감 (시즌별) -----

async def test_rewards_scoped_to_season(client, admin_headers):
    season_id, _, _ = await _season_with_two_teams(client, admin_headers)
    other_id = (
        await client.post(
            "/api/seasons", json={"name": _unique("시즌")}, headers=admin_headers
        )
    ).json()["id"]

    created = await client.post(
        f"/api/seasons/{season_id}/rewards",
        json={"name": "상품권 5만", "total_count": 3},
        headers=admin_headers,
    )
    assert created.status_code == 201
    reward_id = created.json()["id"]
    assert created.json()["season_id"] == season_id

    # 해당 시즌엔 있고
    here = (
        await client.get(f"/api/seasons/{season_id}/rewards", headers=admin_headers)
    ).json()
    assert any(r["id"] == reward_id for r in here)
    # 다른 시즌엔 없다
    there = (
        await client.get(f"/api/seasons/{other_id}/rewards", headers=admin_headers)
    ).json()
    assert all(r["id"] != reward_id for r in there)


async def test_rewards_requires_auth(client):
    res = await client.get("/api/seasons/1/rewards")
    assert res.status_code == 401
