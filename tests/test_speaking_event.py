"""전역 발언권 이벤트 테스트."""

import uuid

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.schemas.speaking import SpeakingEventCreate
from app.services import speaking_service


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _setup_members(client, admin_headers):
    season_id = (
        await client.post(
            "/api/seasons",
            json={"name": _unique("시즌")},
            headers=admin_headers,
        )
    ).json()["id"]
    team_id = (
        await client.post(
            f"/api/seasons/{season_id}/teams",
            json={"name": _unique("팀")},
            headers=admin_headers,
        )
    ).json()["id"]
    user_ids = []
    for idx in range(2):
        user = (
            await client.post(
                "/api/users",
                json={
                    "username": _unique(f"speaker{idx}"),
                    "password": "pw12345678",
                    "nickname": f"참가자{idx + 1}",
                    "role": "user",
                },
                headers=admin_headers,
            )
        ).json()
        user_ids.append(user["id"])
        await client.post(
            f"/api/seasons/{season_id}/teams/{team_id}/members",
            json={"user_id": user["id"]},
            headers=admin_headers,
        )
    return season_id, user_ids


async def _admin_id() -> int:
    async with AsyncSessionLocal() as db:
        admin_id = await db.scalar(select(User.id).where(User.username == "admin"))
        assert admin_id is not None
        return admin_id


async def test_speaking_event_lifecycle_and_grants(client, admin_headers):
    season_id, (u1, u2) = await _setup_members(client, admin_headers)

    res = await client.post(
        f"/api/seasons/{season_id}/speaking-events",
        json={"mode": "speed"},
        headers=admin_headers,
    )
    assert res.status_code == 201
    event_id = res.json()["id"]

    res = await client.post(
        f"/api/seasons/{season_id}/speaking-events",
        json={"mode": "timing", "target_time": 7.5},
        headers=admin_headers,
    )
    assert res.status_code == 409

    async with AsyncSessionLocal() as db:
        event = await speaking_service.get_event(db, event_id)
        await speaking_service.record_once(db, event, u1, 320)
        await speaking_service.record_once(db, event, u2, 240)

    closed = await client.post(
        f"/api/speaking-events/{event_id}/close",
        headers=admin_headers,
    )
    assert closed.status_code == 200
    results = closed.json()["results"]
    assert [r["user_id"] for r in results] == [u2, u1]
    assert [r["rank"] for r in results] == [1, 2]

    grant = await client.post(
        f"/api/speaking-events/{event_id}/grants",
        json={"user_id": u2},
        headers=admin_headers,
    )
    assert grant.status_code == 201
    assert grant.json()["user_id"] == u2

    duplicate = await client.post(
        f"/api/speaking-events/{event_id}/grants",
        json={"user_id": u2},
        headers=admin_headers,
    )
    assert duplicate.status_code == 409


async def test_speaking_count_and_timing_results(client, admin_headers):
    season_id, (u1, u2) = await _setup_members(client, admin_headers)
    admin_id = await _admin_id()

    async with AsyncSessionLocal() as db:
        count_event = await speaking_service.create_event(
            db,
            season_id,
            SpeakingEventCreate(mode="count", duration=5),
            admin_id,
        )
        await speaking_service.record_count(db, count_event, u1)
        await speaking_service.record_count(db, count_event, u1)
        await speaking_service.record_count(db, count_event, u2)
        count_event = await speaking_service.close_event(db, count_event, admin_id)
        count_results = await speaking_service.get_results(db, count_event)

        assert [(r.user_id, r.value, r.rank) for r in count_results] == [
            (u1, 2.0, 1),
            (u2, 1.0, 2),
        ]

        timing_event = await speaking_service.create_event(
            db,
            season_id,
            SpeakingEventCreate(mode="timing", target_time=7.5),
            admin_id,
        )
        await speaking_service.record_once(db, timing_event, u1, 8.2)
        await speaking_service.record_once(db, timing_event, u2, 7.4)
        timing_event = await speaking_service.close_event(db, timing_event, admin_id)
        timing_results = await speaking_service.get_results(db, timing_event)

        assert [(r.user_id, r.value, r.rank) for r in timing_results] == [
            (u2, 0.1, 1),
            (u1, 0.7, 2),
        ]


async def test_speaking_dismiss_requires_admin_and_broadcasts(
    client, admin_headers, user_headers, monkeypatch
):
    season_id, _users = await _setup_members(client, admin_headers)
    event = (
        await client.post(
            f"/api/seasons/{season_id}/speaking-events",
            json={"mode": "speed"},
            headers=admin_headers,
        )
    ).json()
    event_id = event["id"]
    calls = []

    async def fake_broadcast(event):
        calls.append((event.id, event.season_id))

    monkeypatch.setattr(
        "app.api.speaking.broadcast_speaking_event_dismissed",
        fake_broadcast,
    )

    forbidden = await client.post(
        f"/api/speaking-events/{event_id}/dismiss",
        headers=user_headers,
    )
    assert forbidden.status_code == 403

    missing = await client.post(
        "/api/speaking-events/99999999/dismiss",
        headers=admin_headers,
    )
    assert missing.status_code == 404

    dismissed = await client.post(
        f"/api/speaking-events/{event_id}/dismiss",
        headers=admin_headers,
    )
    assert dismissed.status_code == 202
    assert dismissed.json() == {"status": "dismissed"}
    assert calls == [(event_id, season_id)]
