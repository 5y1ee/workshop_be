"""게임 세션 상태 머신 테스트."""

import uuid

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.game_session import GameSession


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _make_timetable_entry(client, admin_headers) -> int:
    season_id = (
        await client.post(
            "/api/seasons", json={"name": _unique("시즌")}, headers=admin_headers
        )
    ).json()["id"]
    game_id = (
        await client.post(
            "/api/games",
            json={"title": _unique("게임"), "participant_type": "team_vs", "input_type": "chat"},
            headers=admin_headers,
        )
    ).json()["id"]
    entry = await client.post(
        f"/api/seasons/{season_id}/timetable",
        json={"game_id": game_id, "order_index": 1},
        headers=admin_headers,
    )
    return entry.json()["id"]


async def _create_session(client, admin_headers) -> int:
    timetable_id = await _make_timetable_entry(client, admin_headers)
    res = await client.post(
        f"/api/timetable/{timetable_id}/session", headers=admin_headers
    )
    assert res.status_code == 201
    assert res.json()["state"] == "idle"
    return res.json()["id"]


async def _transition(client, admin_headers, session_id, to):
    return await client.post(
        f"/api/sessions/{session_id}/transition", json={"to": to}, headers=admin_headers
    )


async def test_full_lifecycle(client, admin_headers):
    session_id = await _create_session(client, admin_headers)

    res = await _transition(client, admin_headers, session_id, "ready")
    assert res.status_code == 200 and res.json()["state"] == "ready"

    res = await _transition(client, admin_headers, session_id, "in_progress")
    assert res.status_code == 200
    body = res.json()
    assert body["state"] == "in_progress"
    assert body["started_at"] is not None  # 시작 시각 자동 기록

    res = await _transition(client, admin_headers, session_id, "scoring")
    assert res.json()["state"] == "scoring"

    res = await _transition(client, admin_headers, session_id, "reward")
    assert res.json()["state"] == "reward"

    res = await _transition(client, admin_headers, session_id, "done")
    assert res.status_code == 200
    assert res.json()["state"] == "done"
    assert res.json()["ended_at"] is not None  # 종료 시각 자동 기록


async def test_create_session_broadcasts(client, admin_headers, monkeypatch):
    from app.api import game_session as game_session_api

    calls: list[dict] = []

    async def fake_broadcast(session) -> None:
        calls.append(
            {
                "session_id": session.id,
                "timetable_id": session.timetable_id,
                "state": session.state,
            }
        )

    monkeypatch.setattr(game_session_api, "broadcast_session_created", fake_broadcast)

    timetable_id = await _make_timetable_entry(client, admin_headers)
    res = await client.post(
        f"/api/timetable/{timetable_id}/session", headers=admin_headers
    )

    assert res.status_code == 201
    body = res.json()
    assert calls == [
        {
            "session_id": body["id"],
            "timetable_id": timetable_id,
            "state": "idle",
        }
    ]


async def test_seed_generated_on_in_progress(client, admin_headers):
    """in_progress 진입 시 서버 시드가 생성되어야 한다 (응답엔 미노출, DB 직접 확인)."""
    session_id = await _create_session(client, admin_headers)
    await _transition(client, admin_headers, session_id, "ready")
    await _transition(client, admin_headers, session_id, "in_progress")

    # 응답 스키마에 seed 가 노출되지 않음을 확인
    res = await client.get(f"/api/sessions/{session_id}", headers=admin_headers)
    assert "seed" not in res.json()

    # DB 에는 시드가 채워져 있어야 함
    async with AsyncSessionLocal() as db:
        session = (
            await db.execute(select(GameSession).where(GameSession.id == session_id))
        ).scalar_one()
        assert session.seed is not None
        assert len(session.seed) == 32  # token_hex(16)


async def test_scoring_can_skip_to_done(client, admin_headers):
    session_id = await _create_session(client, admin_headers)
    for state in ("ready", "in_progress", "scoring"):
        await _transition(client, admin_headers, session_id, state)
    res = await _transition(client, admin_headers, session_id, "done")
    assert res.status_code == 200
    assert res.json()["state"] == "done"


async def test_invalid_transition_409(client, admin_headers):
    session_id = await _create_session(client, admin_headers)
    # idle → done 은 불가
    res = await _transition(client, admin_headers, session_id, "done")
    assert res.status_code == 409


async def test_unknown_target_state_422(client, admin_headers):
    session_id = await _create_session(client, admin_headers)
    res = await _transition(client, admin_headers, session_id, "bogus")
    assert res.status_code == 422


async def test_transition_from_done_is_terminal(client, admin_headers):
    session_id = await _create_session(client, admin_headers)
    for state in ("ready", "in_progress", "scoring", "done"):
        await _transition(client, admin_headers, session_id, state)
    # done 에서는 어떤 전이도 불가
    res = await _transition(client, admin_headers, session_id, "ready")
    assert res.status_code == 409


async def test_create_session_unknown_timetable_404(client, admin_headers):
    res = await client.post("/api/timetable/99999999/session", headers=admin_headers)
    assert res.status_code == 404


async def test_get_session_404(client, admin_headers):
    res = await client.get("/api/sessions/99999999", headers=admin_headers)
    assert res.status_code == 404


async def test_transition_requires_admin(client, admin_headers, user_headers):
    session_id = await _create_session(client, admin_headers)
    res = await client.post(
        f"/api/sessions/{session_id}/transition",
        json={"to": "ready"},
        headers=user_headers,
    )
    assert res.status_code == 403
