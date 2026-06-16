"""점수(game_score_logs) / 결과(game_results) 기록 API 테스트."""

import uuid

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.services import game_round_service


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _setup(client, admin_headers, participant_type: str = "team_vs"):
    """season → team → game → timetable → session, 그리고 user 한 명을 만든다."""
    season_id = (
        await client.post(
            "/api/seasons", json={"name": _unique("시즌")}, headers=admin_headers
        )
    ).json()["id"]
    team_id = (
        await client.post(
            f"/api/seasons/{season_id}/teams",
            json={"name": "레드팀"},
            headers=admin_headers,
        )
    ).json()["id"]
    game_id = (
        await client.post(
            "/api/games",
            json={
                "title": _unique("게임"),
                "participant_type": participant_type,
                "input_type": "chat",
            },
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
    session_id = (
        await client.post(
            f"/api/timetable/{timetable_id}/session", headers=admin_headers
        )
    ).json()["id"]
    user_id = (
        await client.post(
            "/api/users",
            json={
                "username": _unique("p"),
                "password": "pw12345678",
                "nickname": "참가자",
                "role": "user",
            },
            headers=admin_headers,
        )
    ).json()["id"]
    await client.post(
        f"/api/seasons/{season_id}/teams/{team_id}/members",
        json={"user_id": user_id},
        headers=admin_headers,
    )
    return session_id, team_id, user_id


async def _create_chat_log(client, admin_headers, session_id: int, answer: str) -> int:
    round_id = (
        await client.post(
            f"/api/sessions/{session_id}/rounds",
            json={"order_index": 1, "prompt": "제목은?", "correct_answer": "봄날"},
            headers=admin_headers,
        )
    ).json()["id"]
    await client.post(
        f"/api/sessions/{session_id}/transition",
        json={"to": "ready"},
        headers=admin_headers,
    )
    await client.post(f"/api/rounds/{round_id}/open", headers=admin_headers)

    async with AsyncSessionLocal() as db:
        user = User(
            username=_unique("chat"),
            password=hash_password("pw12345678"),
            nickname="채팅참가자",
            role="user",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        round_ = await game_round_service.get_open_round(db, session_id)
        chat = await game_round_service.record_chat(db, session_id, round_, user.id, answer)
        return chat.id


# ----- Scores -----

async def test_create_score_for_team_and_user(client, admin_headers):
    session_id, team_id, user_id = await _setup(client, admin_headers)

    res = await client.post(
        f"/api/sessions/{session_id}/scores",
        json={"subject_type": "team", "subject_id": team_id, "score": 10, "memo": "1위"},
        headers=admin_headers,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["subject_type"] == "team"
    assert body["score"] == 10
    assert body["created_by"] is not None

    res = await client.post(
        f"/api/sessions/{session_id}/scores",
        json={"subject_type": "user", "subject_id": user_id, "score": 3},
        headers=admin_headers,
    )
    assert res.status_code == 201
    assert res.json()["subject_type"] == "user"

    user_session_id, user_team_id, user_id = await _setup(
        client, admin_headers, participant_type="individual"
    )
    res = await client.post(
        f"/api/sessions/{user_session_id}/scores",
        json={"subject_type": "user", "subject_id": user_id, "score": 3},
        headers=admin_headers,
    )
    assert res.status_code == 201

    res = await client.post(
        f"/api/sessions/{user_session_id}/scores",
        json={"subject_type": "team", "subject_id": user_team_id, "score": 5},
        headers=admin_headers,
    )
    assert res.status_code == 201


async def test_create_score_with_correct_chat_log(client, admin_headers):
    session_id, team_id, _ = await _setup(client, admin_headers)
    chat_log_id = await _create_chat_log(client, admin_headers, session_id, "봄날")

    res = await client.post(
        f"/api/sessions/{session_id}/scores",
        json={
            "subject_type": "team",
            "subject_id": team_id,
            "score": 10,
            "chat_log_id": chat_log_id,
        },
        headers=admin_headers,
    )
    assert res.status_code == 201
    assert res.json()["chat_log_id"] == chat_log_id


async def test_create_score_with_same_chat_log_conflicts(client, admin_headers):
    session_id, team_id, _ = await _setup(client, admin_headers)
    chat_log_id = await _create_chat_log(client, admin_headers, session_id, "봄날")
    payload = {
        "subject_type": "team",
        "subject_id": team_id,
        "score": 10,
        "chat_log_id": chat_log_id,
    }
    assert (
        await client.post(
            f"/api/sessions/{session_id}/scores",
            json=payload,
            headers=admin_headers,
        )
    ).status_code == 201

    res = await client.post(
        f"/api/sessions/{session_id}/scores",
        json=payload,
        headers=admin_headers,
    )
    assert res.status_code == 409


async def test_create_score_with_wrong_chat_log_rejected(client, admin_headers):
    session_id, team_id, _ = await _setup(client, admin_headers)
    chat_log_id = await _create_chat_log(client, admin_headers, session_id, "여름밤")

    res = await client.post(
        f"/api/sessions/{session_id}/scores",
        json={
            "subject_type": "team",
            "subject_id": team_id,
            "score": 10,
            "chat_log_id": chat_log_id,
        },
        headers=admin_headers,
    )
    assert res.status_code == 400


async def test_create_score_with_other_session_chat_log_rejected(client, admin_headers):
    session_id, team_id, _ = await _setup(client, admin_headers)
    other_session_id, _, _ = await _setup(client, admin_headers)
    chat_log_id = await _create_chat_log(client, admin_headers, other_session_id, "봄날")

    res = await client.post(
        f"/api/sessions/{session_id}/scores",
        json={
            "subject_type": "team",
            "subject_id": team_id,
            "score": 10,
            "chat_log_id": chat_log_id,
        },
        headers=admin_headers,
    )
    assert res.status_code == 400


async def test_score_summary_aggregates(client, admin_headers):
    session_id, team_id, _ = await _setup(client, admin_headers)

    for sc in (10, 5):
        await client.post(
            f"/api/sessions/{session_id}/scores",
            json={"subject_type": "team", "subject_id": team_id, "score": sc},
            headers=admin_headers,
        )

    res = await client.get(
        f"/api/sessions/{session_id}/scores/summary", headers=admin_headers
    )
    assert res.status_code == 200
    summary = res.json()
    assert summary == [{
        "subject_type": "team",
        "subject_id": team_id,
        "subject_name": "레드팀",
        "total_score": 15,
    }]

    user_session_id, _, user_id = await _setup(
        client, admin_headers, participant_type="individual"
    )
    await client.post(
        f"/api/sessions/{user_session_id}/scores",
        json={"subject_type": "user", "subject_id": user_id, "score": 3},
        headers=admin_headers,
    )
    res = await client.get(
        f"/api/sessions/{user_session_id}/scores/summary", headers=admin_headers
    )
    assert res.status_code == 200
    summary = res.json()
    assert {
        "subject_type": "user",
        "subject_id": user_id,
        "subject_name": "참가자",
        "total_score": 3,
    } in summary


async def test_list_and_update_score(client, admin_headers):
    session_id, team_id, _ = await _setup(client, admin_headers)
    score_id = (
        await client.post(
            f"/api/sessions/{session_id}/scores",
            json={"subject_type": "team", "subject_id": team_id, "score": 7},
            headers=admin_headers,
        )
    ).json()["id"]

    res = await client.get(f"/api/sessions/{session_id}/scores", headers=admin_headers)
    assert [s["id"] for s in res.json()] == [score_id]

    res = await client.patch(
        f"/api/scores/{score_id}", json={"score": 99, "memo": "정정"}, headers=admin_headers
    )
    assert res.status_code == 200
    assert res.json()["score"] == 99
    assert res.json()["updated_at"] is not None


async def test_score_unknown_session_404(client, admin_headers):
    res = await client.post(
        "/api/sessions/99999999/scores",
        json={"subject_type": "team", "subject_id": 1, "score": 1},
        headers=admin_headers,
    )
    assert res.status_code == 404


async def test_score_unknown_subject_400(client, admin_headers):
    session_id, _, _ = await _setup(client, admin_headers)
    res = await client.post(
        f"/api/sessions/{session_id}/scores",
        json={"subject_type": "team", "subject_id": 99999999, "score": 1},
        headers=admin_headers,
    )
    assert res.status_code == 400


async def test_score_invalid_subject_type_422(client, admin_headers):
    session_id, team_id, _ = await _setup(client, admin_headers)
    res = await client.post(
        f"/api/sessions/{session_id}/scores",
        json={"subject_type": "robot", "subject_id": team_id, "score": 1},
        headers=admin_headers,
    )
    assert res.status_code == 422


async def test_score_create_requires_admin(client, admin_headers, user_headers):
    session_id, team_id, _ = await _setup(client, admin_headers)
    res = await client.post(
        f"/api/sessions/{session_id}/scores",
        json={"subject_type": "team", "subject_id": team_id, "score": 1},
        headers=user_headers,
    )
    assert res.status_code == 403


# ----- Results -----

async def test_create_and_list_result(client, admin_headers):
    session_id, team_id, _ = await _setup(client, admin_headers)
    res = await client.post(
        f"/api/sessions/{session_id}/results",
        json={"subject_type": "team", "subject_id": team_id},
        headers=admin_headers,
    )
    assert res.status_code == 201
    assert res.json()["subject_id"] == team_id

    res = await client.get(f"/api/sessions/{session_id}/results", headers=admin_headers)
    assert res.status_code == 200
    assert len(res.json()) == 1


async def test_result_unknown_subject_400(client, admin_headers):
    session_id, _, _ = await _setup(client, admin_headers)
    res = await client.post(
        f"/api/sessions/{session_id}/results",
        json={"subject_type": "user", "subject_id": 99999999},
        headers=admin_headers,
    )
    assert res.status_code == 400


# ----- 브로드캐스트 -----

async def test_score_and_result_broadcast(client, admin_headers, monkeypatch):
    from app.websocket import manager as mgr_mod

    calls: list[dict] = []

    async def fake_broadcast(message: dict) -> None:
        calls.append(message)

    monkeypatch.setattr(mgr_mod.manager, "broadcast", fake_broadcast)

    session_id, team_id, _ = await _setup(client, admin_headers)
    await client.post(
        f"/api/sessions/{session_id}/scores",
        json={"subject_type": "team", "subject_id": team_id, "score": 8},
        headers=admin_headers,
    )
    await client.post(
        f"/api/sessions/{session_id}/results",
        json={"subject_type": "team", "subject_id": team_id},
        headers=admin_headers,
    )

    types = [c["type"] for c in calls]
    assert "score_recorded" in types
    assert "result_recorded" in types
