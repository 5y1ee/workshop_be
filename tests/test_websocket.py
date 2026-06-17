"""WebSocket 메시지 핸들러 + 상태 전이 브로드캐스트 테스트."""

import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.main import app
from app.websocket.handlers import MessageContext, dispatch


def _token() -> str:
    return create_access_token(subject=1, role="admin", team_id=None)


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ---- dispatch 단위 테스트 (순수) ----

class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)


async def test_dispatch_ping():
    ws = _FakeWS()
    ctx = MessageContext(websocket=ws, manager=None, user_id=1, team_id=None)
    await dispatch(ctx, {"type": "ping"})
    assert ws.sent == [{"type": "pong"}]


async def test_dispatch_unknown_type():
    ws = _FakeWS()
    ctx = MessageContext(websocket=ws, manager=None, user_id=1, team_id=None)
    await dispatch(ctx, {"type": "floop"})
    assert ws.sent[0]["type"] == "error"


# ---- 실제 WebSocket 연결 (동기 TestClient) ----

def test_ws_ping_pong():
    with TestClient(app) as c:
        with c.websocket_connect(f"/ws?token={_token()}") as ws:
            ws.send_json({"type": "ping"})
            assert ws.receive_json() == {"type": "pong"}


def test_ws_unknown_type_returns_error():
    with TestClient(app) as c:
        with c.websocket_connect(f"/ws?token={_token()}") as ws:
            ws.send_json({"type": "nope"})
            msg = ws.receive_json()
            assert msg["type"] == "error"


def test_ws_invalid_token_rejected():
    with TestClient(app) as c:
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect("/ws?token=invalid") as ws:
                ws.receive_json()


# ---- 상태 전이 → 브로드캐스트 ----

async def test_transition_broadcasts_state(client, admin_headers, monkeypatch):
    from app.websocket import manager as mgr_mod

    calls: list[dict] = []

    async def fake_broadcast(message: dict) -> None:
        calls.append(message)

    monkeypatch.setattr(mgr_mod.manager, "broadcast", fake_broadcast)

    # 세션 준비
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

    # 전이 → 브로드캐스트 발생
    res = await client.post(
        f"/api/sessions/{session_id}/transition",
        json={"to": "ready"},
        headers=admin_headers,
    )
    assert res.status_code == 200

    assert any(
        c["type"] == "session_state_changed"
        and c["session_id"] == session_id
        and c["state"] == "ready"
        for c in calls
    )


async def test_chat_broadcast_includes_log_id(monkeypatch):
    from app.websocket import events

    calls: list[tuple[int, dict]] = []

    async def fake_broadcast_to_session(session_id: int, message: dict) -> None:
        calls.append((session_id, message))

    monkeypatch.setattr(events.manager, "broadcast_to_session", fake_broadcast_to_session)

    chat = SimpleNamespace(
        id=33,
        session_id=7,
        round_id=2,
        user_id=5,
        message="봄날",
        is_correct=True,
        server_time=datetime(2026, 6, 16, 4, 0, 0),
    )
    await events.broadcast_chat_message(chat, "민지")

    assert calls == [
        (
            7,
            {
                "type": "chat_message",
                "id": 33,
                "session_id": 7,
                "round_id": 2,
                "user_id": 5,
                "nickname": "민지",
                "message": "봄날",
                "is_correct": True,
                "server_time": "2026-06-16T04:00:00Z",
            },
        )
    ]


async def test_session_created_broadcast(monkeypatch):
    from app.websocket import events

    calls: list[dict] = []

    async def fake_broadcast(message: dict) -> None:
        calls.append(message)

    monkeypatch.setattr(events.manager, "broadcast", fake_broadcast)

    session = SimpleNamespace(id=11, timetable_id=22, state="idle")
    await events.broadcast_session_created(session)

    assert calls == [
        {
            "type": "session_created",
            "session_id": 11,
            "timetable_id": 22,
            "state": "idle",
        }
    ]


async def test_score_changed_broadcast(monkeypatch):
    from app.websocket import events

    calls: list[dict] = []

    async def fake_broadcast(message: dict) -> None:
        calls.append(message)

    monkeypatch.setattr(events.manager, "broadcast", fake_broadcast)

    score = SimpleNamespace(
        id=31,
        session_id=7,
        subject_type="team",
        subject_id=5,
        chat_log_id=None,
        score=12,
    )
    await events.broadcast_score_changed(score, "updated")

    assert calls == [
        {
            "type": "score_changed",
            "session_id": 7,
            "score_id": 31,
            "subject_type": "team",
            "subject_id": 5,
            "chat_log_id": None,
            "score": 12,
            "action": "updated",
        }
    ]


async def test_team_membership_changed_broadcast(monkeypatch):
    from app.websocket import events

    calls: list[dict] = []

    async def fake_broadcast(message: dict) -> None:
        calls.append(message)

    monkeypatch.setattr(events.manager, "broadcast", fake_broadcast)

    await events.broadcast_team_membership_changed(1, 2, 3, "assigned")

    assert calls == [
        {
            "type": "team_membership_changed",
            "season_id": 1,
            "user_id": 2,
            "team_id": 3,
            "action": "assigned",
        }
    ]


async def test_reward_catalog_changed_broadcast(monkeypatch):
    from app.websocket import events

    calls: list[dict] = []

    async def fake_broadcast(message: dict) -> None:
        calls.append(message)

    monkeypatch.setattr(events.manager, "broadcast", fake_broadcast)

    await events.broadcast_reward_catalog_changed(1, 9, "deleted")

    assert calls == [
        {
            "type": "reward_catalog_changed",
            "season_id": 1,
            "reward_id": 9,
            "action": "deleted",
        }
    ]
