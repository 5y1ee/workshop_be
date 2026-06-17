"""시즌별 실시간 공지 API 테스트."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.notice import Notice
from app.models.user import User


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_season(client, admin_headers) -> int:
    res = await client.post(
        "/api/seasons", json={"name": _unique("시즌")}, headers=admin_headers
    )
    return res.json()["id"]


async def _admin_id() -> int:
    async with AsyncSessionLocal() as db:
        user_id = await db.scalar(select(User.id).where(User.username == "admin"))
        assert user_id is not None
        return user_id


async def test_notice_create_replace_current_delete_and_broadcast(
    client, admin_headers, user_headers, monkeypatch
):
    from app.websocket import events

    calls: list[dict] = []

    async def fake_broadcast(message: dict) -> None:
        calls.append(message)

    monkeypatch.setattr(events.manager, "broadcast", fake_broadcast)

    season_id = await _create_season(client, admin_headers)
    empty = await client.get(
        f"/api/seasons/{season_id}/notices/current", headers=user_headers
    )
    assert empty.status_code == 200
    assert empty.json()["notice"] is None

    first = await client.post(
        f"/api/seasons/{season_id}/notices",
        json={"message": "첫 공지", "duration_minutes": 10},
        headers=admin_headers,
    )
    assert first.status_code == 201
    first_id = first.json()["id"]
    assert calls[-1]["type"] == "notice_created"
    assert calls[-1]["notice"]["message"] == "첫 공지"

    second = await client.post(
        f"/api/seasons/{season_id}/notices",
        json={"message": "교체 공지", "duration_minutes": 5},
        headers=admin_headers,
    )
    assert second.status_code == 201
    second_id = second.json()["id"]

    current = await client.get(
        f"/api/seasons/{season_id}/notices/current", headers=user_headers
    )
    assert current.json()["notice"]["id"] == second_id
    assert current.json()["notice"]["message"] == "교체 공지"

    listed = await client.get(
        f"/api/seasons/{season_id}/notices", headers=admin_headers
    )
    assert [row["id"] for row in listed.json()] == [second_id]

    deleted_old = await client.delete(f"/api/notices/{first_id}", headers=admin_headers)
    assert deleted_old.status_code == 204

    deleted = await client.delete(f"/api/notices/{second_id}", headers=admin_headers)
    assert deleted.status_code == 204
    assert calls[-1] == {
        "type": "notice_deleted",
        "season_id": season_id,
        "notice_id": second_id,
    }

    current = await client.get(
        f"/api/seasons/{season_id}/notices/current", headers=user_headers
    )
    assert current.json()["notice"] is None


async def test_notice_list_requires_admin_and_current_excludes_expired(
    client, admin_headers, user_headers
):
    season_id = await _create_season(client, admin_headers)
    admin_id = await _admin_id()
    past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)

    async with AsyncSessionLocal() as db:
        db.add(
            Notice(
                season_id=season_id,
                message="만료 공지",
                expires_at=past,
                created_by=admin_id,
            )
        )
        await db.commit()

    current = await client.get(
        f"/api/seasons/{season_id}/notices/current", headers=user_headers
    )
    assert current.status_code == 200
    assert current.json()["notice"] is None

    listed = await client.get(
        f"/api/seasons/{season_id}/notices", headers=user_headers
    )
    assert listed.status_code == 403
