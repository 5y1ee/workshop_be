"""게임 라운드(세션 내부 진행도) 테스트.

라운드 REST API + 제출/채팅 서비스 로직(DB 데이터 직접 삽입)을 검증한다.
"""

import uuid

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.services import game_round_service
from app.services.game_round_service import RoundConflict


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _button_session(client, admin_headers, input_type: str = "button") -> int:
    """button/chat 게임 + 타임테이블 + 세션을 만들고 session_id 를 돌려준다."""
    season_id = (
        await client.post(
            "/api/seasons", json={"name": _unique("시즌")}, headers=admin_headers
        )
    ).json()["id"]
    game_id = (
        await client.post(
            "/api/games",
            json={
                "title": _unique("게임"),
                "participant_type": "team_vs",
                "input_type": input_type,
            },
            headers=admin_headers,
        )
    ).json()["id"]
    entry_id = (
        await client.post(
            f"/api/seasons/{season_id}/timetable",
            json={"game_id": game_id, "order_index": 1},
            headers=admin_headers,
        )
    ).json()["id"]
    res = await client.post(f"/api/timetable/{entry_id}/session", headers=admin_headers)
    return res.json()["id"]


async def _make_user() -> int:
    """제출용 더미 유저를 DB 에 직접 만들고 id 를 돌려준다."""
    async with AsyncSessionLocal() as db:
        u = User(
            username=_unique("u"),
            password=hash_password("pw1234"),
            nickname=_unique("닉"),
            role="user",
        )
        db.add(u)
        await db.commit()
        await db.refresh(u)
        return u.id


async def _create_round(client, admin_headers, session_id, **body):
    body.setdefault("order_index", 1)
    return await client.post(
        f"/api/sessions/{session_id}/rounds", json=body, headers=admin_headers
    )


# ---------------------------------------------------------------------------
# REST: 생성 / 정답 비노출 / open 단일성 / current / close→reveal
# ---------------------------------------------------------------------------


async def test_round_create_hides_correct_answer(client, admin_headers):
    session_id = await _button_session(client, admin_headers)
    res = await _create_round(
        client,
        admin_headers,
        session_id,
        prompt="수도는?",
        options=["서울", "부산"],
        correct_answer="서울",
    )
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "waiting"
    assert body["options"] == ["서울", "부산"]
    # 정답은 룰렛 seed 처럼 플레이어 응답에서 비노출
    assert "correct_answer" not in body


async def test_only_one_open_round_per_session(client, admin_headers):
    session_id = await _button_session(client, admin_headers)
    r1 = (await _create_round(client, admin_headers, session_id, order_index=1)).json()
    r2 = (await _create_round(client, admin_headers, session_id, order_index=2)).json()

    assert (await client.post(f"/api/rounds/{r1['id']}/open", headers=admin_headers)).status_code == 200
    # 이미 열린 라운드가 있으면 두 번째 open 은 409
    assert (await client.post(f"/api/rounds/{r2['id']}/open", headers=admin_headers)).status_code == 409

    # current 는 열린 r1 을 가리킨다
    cur = await client.get(f"/api/sessions/{session_id}/rounds/current", headers=admin_headers)
    assert cur.status_code == 200 and cur.json()["id"] == r1["id"]


async def test_current_round_404_when_none_open(client, admin_headers):
    session_id = await _button_session(client, admin_headers)
    await _create_round(client, admin_headers, session_id)
    res = await client.get(f"/api/sessions/{session_id}/rounds/current", headers=admin_headers)
    assert res.status_code == 404


async def test_submit_judge_dedupe_and_reveal(client, admin_headers):
    session_id = await _button_session(client, admin_headers)
    r = (
        await _create_round(
            client,
            admin_headers,
            session_id,
            prompt="수도는?",
            options=["서울", "부산", "인천", "대전"],
            correct_answer="서울",
        )
    ).json()
    await client.post(f"/api/rounds/{r['id']}/open", headers=admin_headers)

    u_correct = await _make_user()
    u_wrong = await _make_user()

    # 제출은 WebSocket 핸들러가 쓰는 서비스 로직으로 직접 검증
    async with AsyncSessionLocal() as db:
        round_ = await game_round_service.get_round(db, r["id"])
        s1 = await game_round_service.submit_answer(db, round_, u_correct, "서울")
        assert s1.is_correct is True
        s2 = await game_round_service.submit_answer(db, round_, u_wrong, "부산")
        assert s2.is_correct is False

        # 같은 유저 중복 제출은 충돌
        try:
            await game_round_service.submit_answer(db, round_, u_correct, "인천")
            raise AssertionError("중복 제출이 막히지 않았습니다.")
        except RoundConflict:
            pass

    # 마감 → 정답 + 분포 공개
    reveal = await client.post(f"/api/rounds/{r['id']}/close", headers=admin_headers)
    assert reveal.status_code == 200
    rb = reveal.json()
    assert rb["correct_answer"] == "서울"
    assert rb["total_submissions"] == 2
    assert rb["distribution"] == {"서울": 1, "부산": 1}

    # 마감된 라운드는 다시 열 수 없다
    assert (await client.post(f"/api/rounds/{r['id']}/open", headers=admin_headers)).status_code == 409


async def test_submit_on_unopened_round_conflicts(client, admin_headers):
    session_id = await _button_session(client, admin_headers)
    r = (await _create_round(client, admin_headers, session_id)).json()
    uid = await _make_user()
    async with AsyncSessionLocal() as db:
        round_ = await game_round_service.get_round(db, r["id"])
        try:
            await game_round_service.submit_answer(db, round_, uid, "아무거나")
            raise AssertionError("waiting 라운드 제출이 막히지 않았습니다.")
        except RoundConflict:
            pass


async def test_record_chat_judges_against_open_round(client, admin_headers):
    session_id = await _button_session(client, admin_headers, input_type="chat")
    r = (
        await _create_round(
            client, admin_headers, session_id, prompt="제목은?", correct_answer="봄날"
        )
    ).json()
    await client.post(f"/api/rounds/{r['id']}/open", headers=admin_headers)
    uid = await _make_user()

    async with AsyncSessionLocal() as db:
        round_ = await game_round_service.get_open_round(db, session_id)
        assert round_ is not None
        hit = await game_round_service.record_chat(db, session_id, round_, uid, "  봄날 ")
        assert hit.is_correct is True  # 공백 무시 정답 판정
        miss = await game_round_service.record_chat(db, session_id, round_, uid, "여름밤")
        assert miss.is_correct is False
        assert miss.round_id == round_.id


async def test_round_endpoints_require_admin(client, admin_headers, user_headers):
    session_id = await _button_session(client, admin_headers)
    # 일반 유저는 라운드 생성 불가
    res = await client.post(
        f"/api/sessions/{session_id}/rounds",
        json={"order_index": 1},
        headers=user_headers,
    )
    assert res.status_code == 403
    # 조회는 가능
    res = await client.get(f"/api/sessions/{session_id}/rounds", headers=user_headers)
    assert res.status_code == 200
