"""Game / Timetable 관리 API 테스트."""

import uuid


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_game(client, admin_headers, **overrides):
    payload = {
        "title": _unique("게임"),
        "participant_type": "team_vs",
        "input_type": "chat",
    }
    payload.update(overrides)
    return await client.post("/api/games", json=payload, headers=admin_headers)


async def _create_season(client, admin_headers):
    res = await client.post(
        "/api/seasons", json={"name": _unique("시즌")}, headers=admin_headers
    )
    return res.json()["id"]


# ----- Games -----

async def test_game_crud_flow(client, admin_headers):
    res = await _create_game(client, admin_headers, title="노래맞추기", description="툴팁")
    assert res.status_code == 201
    game = res.json()
    assert game["title"] == "노래맞추기"
    assert game["participant_type"] == "team_vs"
    game_id = game["id"]

    res = await client.get(f"/api/games/{game_id}", headers=admin_headers)
    assert res.status_code == 200

    res = await client.get("/api/games", headers=admin_headers)
    assert any(g["id"] == game_id for g in res.json())

    res = await client.patch(
        f"/api/games/{game_id}",
        json={"input_type": "button", "description": "수정"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["input_type"] == "button"
    assert res.json()["updated_at"] is not None


async def test_game_invalid_enum_422(client, admin_headers):
    res = await _create_game(client, admin_headers, participant_type="solo")
    assert res.status_code == 422
    res = await _create_game(client, admin_headers, input_type="telepathy")
    assert res.status_code == 422


async def test_game_get_404(client, admin_headers):
    res = await client.get("/api/games/99999999", headers=admin_headers)
    assert res.status_code == 404


async def test_game_create_requires_admin(client, user_headers):
    res = await client.post(
        "/api/games",
        json={"title": "x", "participant_type": "team_vs", "input_type": "chat"},
        headers=user_headers,
    )
    assert res.status_code == 403


# ----- Timetable -----

async def test_timetable_crud_flow(client, admin_headers):
    season_id = await _create_season(client, admin_headers)
    game_id = (await _create_game(client, admin_headers)).json()["id"]

    # 항목 추가
    res = await client.post(
        f"/api/seasons/{season_id}/timetable",
        json={"game_id": game_id, "order_index": 1, "label": "메인①", "raffle_reward": 3},
        headers=admin_headers,
    )
    assert res.status_code == 201
    entry = res.json()
    assert entry["season_id"] == season_id
    assert entry["game_id"] == game_id
    assert entry["raffle_reward"] == 3
    assert entry["main_visible"] is True
    entry_id = entry["id"]

    # 단건
    res = await client.get(f"/api/timetable/{entry_id}", headers=admin_headers)
    assert res.status_code == 200

    # 수정
    res = await client.patch(
        f"/api/timetable/{entry_id}",
        json={"order_index": 5, "main_visible": False},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["order_index"] == 5
    assert res.json()["main_visible"] is False

    # 삭제
    res = await client.delete(f"/api/timetable/{entry_id}", headers=admin_headers)
    assert res.status_code == 204
    res = await client.get(f"/api/timetable/{entry_id}", headers=admin_headers)
    assert res.status_code == 404


async def test_timetable_changes_broadcast(client, admin_headers, monkeypatch):
    from app.websocket import events as ws_events

    calls = []

    async def fake_broadcast(season_id: int, entry_id: int | None, action: str) -> None:
        calls.append({"season_id": season_id, "entry_id": entry_id, "action": action})

    monkeypatch.setattr(ws_events, "broadcast_timetable_changed", fake_broadcast)

    season_id = await _create_season(client, admin_headers)
    game_id = (await _create_game(client, admin_headers)).json()["id"]
    created = (
        await client.post(
            f"/api/seasons/{season_id}/timetable",
            json={"game_id": game_id, "order_index": 1},
            headers=admin_headers,
        )
    ).json()
    await client.patch(
        f"/api/timetable/{created['id']}",
        json={"main_visible": False},
        headers=admin_headers,
    )
    await client.delete(f"/api/timetable/{created['id']}", headers=admin_headers)

    assert calls == [
        {"season_id": season_id, "entry_id": created["id"], "action": "created"},
        {"season_id": season_id, "entry_id": created["id"], "action": "updated"},
        {"season_id": season_id, "entry_id": created["id"], "action": "deleted"},
    ]


async def test_timetable_delete_reindexes_and_blocks_started_entry(client, admin_headers):
    season_id = await _create_season(client, admin_headers)
    game_id = (await _create_game(client, admin_headers)).json()["id"]
    ids = []
    for idx in (1, 2, 3):
        ids.append((
            await client.post(
                f"/api/seasons/{season_id}/timetable",
                json={"game_id": game_id, "order_index": idx},
                headers=admin_headers,
            )
        ).json()["id"])

    res = await client.delete(f"/api/timetable/{ids[1]}", headers=admin_headers)
    assert res.status_code == 204
    res = await client.get(f"/api/seasons/{season_id}/timetable", headers=admin_headers)
    assert [e["order_index"] for e in res.json()] == [1, 2]
    assert [e["id"] for e in res.json()] == [ids[0], ids[2]]

    # 세션만 생성되고 아직 시작하지 않은 idle 항목은 삭제 가능
    await client.post(f"/api/timetable/{ids[0]}/session", headers=admin_headers)
    res = await client.delete(f"/api/timetable/{ids[0]}", headers=admin_headers)
    assert res.status_code == 204

    started_id = (
        await client.post(
            f"/api/seasons/{season_id}/timetable",
            json={"game_id": game_id, "order_index": 2},
            headers=admin_headers,
        )
    ).json()["id"]
    session_id = (
        await client.post(f"/api/timetable/{started_id}/session", headers=admin_headers)
    ).json()["id"]
    await client.post(
        f"/api/sessions/{session_id}/transition",
        json={"to": "ready"},
        headers=admin_headers,
    )
    res = await client.delete(f"/api/timetable/{started_id}", headers=admin_headers)
    assert res.status_code == 409


async def test_timetable_ordering(client, admin_headers):
    season_id = await _create_season(client, admin_headers)
    game_id = (await _create_game(client, admin_headers)).json()["id"]

    for idx in (3, 1, 2):
        await client.post(
            f"/api/seasons/{season_id}/timetable",
            json={"game_id": game_id, "order_index": idx},
            headers=admin_headers,
        )

    res = await client.get(f"/api/seasons/{season_id}/timetable", headers=admin_headers)
    assert res.status_code == 200
    assert [e["order_index"] for e in res.json()] == [1, 2, 3]


async def test_timetable_unknown_season_404(client, admin_headers):
    game_id = (await _create_game(client, admin_headers)).json()["id"]
    res = await client.post(
        "/api/seasons/99999999/timetable",
        json={"game_id": game_id, "order_index": 1},
        headers=admin_headers,
    )
    assert res.status_code == 404


async def test_timetable_unknown_game_400(client, admin_headers):
    season_id = await _create_season(client, admin_headers)
    res = await client.post(
        f"/api/seasons/{season_id}/timetable",
        json={"game_id": 99999999, "order_index": 1},
        headers=admin_headers,
    )
    assert res.status_code == 400


async def test_timetable_create_requires_admin(client, admin_headers, user_headers):
    season_id = await _create_season(client, admin_headers)
    game_id = (await _create_game(client, admin_headers)).json()["id"]
    res = await client.post(
        f"/api/seasons/{season_id}/timetable",
        json={"game_id": game_id, "order_index": 1},
        headers=user_headers,
    )
    assert res.status_code == 403
