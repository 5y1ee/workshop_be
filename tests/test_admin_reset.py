async def test_reset_operational_data_requires_admin(client, user_headers):
    res = await client.post(
        "/api/admin/reset-operational-data",
        json={"confirm": True},
        headers=user_headers,
    )

    assert res.status_code == 403


async def test_reset_operational_data_requires_confirmation(client, admin_headers):
    res = await client.post(
        "/api/admin/reset-operational-data",
        json={"confirm": False},
        headers=admin_headers,
    )

    assert res.status_code == 400


async def test_reset_operational_data_runs_operational_seed(
    client, admin_headers, monkeypatch
):
    from app.api import admin as admin_api

    calls: list[str] = []

    async def fake_reset() -> None:
        calls.append("reset")

    async def fake_seed(*, include_demo_details: bool = True) -> None:
        calls.append(f"seed:{include_demo_details}")

    monkeypatch.setattr(admin_api.seed_db, "reset", fake_reset)
    monkeypatch.setattr(admin_api.seed_db, "seed", fake_seed)

    res = await client.post(
        "/api/admin/reset-operational-data",
        json={"confirm": True},
        headers=admin_headers,
    )

    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert calls == ["reset", "seed:False"]
