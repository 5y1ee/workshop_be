"""게임 세션 내부 라운드(진행도) 비즈니스 로직.

세션당 동시에 1개의 라운드만 'open' 상태일 수 있다.
"""

import asyncio
import random
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.game_round import GameRound, RoundSubmission, TapLog
from app.models.game_session import GameChatLog, GameSession
from app.models.team import Team
from app.models.team_member import TeamMembership
from app.models.timetable import Timetable
from app.models.user import User
from app.schemas.game_round import RoundCreate, RoundUpdate, TapResult


class RoundConflict(Exception):
    """라운드 상태/제출 충돌 (이미 마감, 중복 제출 등)."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _judge(correct: str | None, answer: str) -> bool:
    """정답 판정. 앞뒤 공백 무시 + 대소문자 무시."""
    if correct is None:
        return False
    return correct.strip().casefold() == answer.strip().casefold()


# --- 조회/생성 ---------------------------------------------------------------


async def create_round(
    db: AsyncSession, session_id: int, data: RoundCreate, admin_id: int
) -> GameRound:
    round_ = GameRound(
        session_id=session_id,
        order_index=data.order_index,
        prompt=data.prompt,
        media_url=data.media_url,
        options=data.options,
        correct_answer=data.correct_answer,
        tap_mode=data.tap_mode,
        duration=data.duration,
        target_time=data.target_time,
        created_by=admin_id,
    )
    db.add(round_)
    await db.commit()
    await db.refresh(round_)
    return round_


async def list_rounds(db: AsyncSession, session_id: int) -> list[GameRound]:
    result = await db.execute(
        select(GameRound)
        .where(GameRound.session_id == session_id)
        .order_by(GameRound.order_index)
    )
    return list(result.scalars().all())


async def get_round(db: AsyncSession, round_id: int) -> GameRound | None:
    result = await db.execute(select(GameRound).where(GameRound.id == round_id))
    return result.scalar_one_or_none()


async def get_open_round(db: AsyncSession, session_id: int) -> GameRound | None:
    """세션에서 현재 진행 중(open)인 라운드. 없으면 None."""
    result = await db.execute(
        select(GameRound).where(
            GameRound.session_id == session_id, GameRound.status == "open"
        )
    )
    return result.scalar_one_or_none()


async def list_chat_logs(
    db: AsyncSession, session_id: int, round_id: int | None = None
) -> list[dict]:
    """운영자용 채팅 로그. 서버 저장 순서로 빠른 답변 순위를 판단한다."""
    stmt = (
        select(
            GameChatLog.id,
            GameChatLog.session_id,
            GameChatLog.round_id,
            GameChatLog.user_id,
            User.nickname,
            Team.id.label("team_id"),
            Team.name.label("team_name"),
            GameChatLog.message,
            GameChatLog.is_correct,
            GameChatLog.server_time,
        )
        .join(User, User.id == GameChatLog.user_id)
        .join(GameSession, GameSession.id == GameChatLog.session_id)
        .join(Timetable, Timetable.id == GameSession.timetable_id)
        .outerjoin(
            TeamMembership,
            and_(
                TeamMembership.season_id == Timetable.season_id,
                TeamMembership.user_id == GameChatLog.user_id,
            ),
        )
        .outerjoin(Team, Team.id == TeamMembership.team_id)
        .where(GameChatLog.session_id == session_id)
        .order_by(GameChatLog.server_time, GameChatLog.id)
    )
    if round_id is not None:
        stmt = stmt.where(GameChatLog.round_id == round_id)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def update_round(
    db: AsyncSession, round_: GameRound, data: RoundUpdate, admin_id: int
) -> GameRound:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(round_, key, value)
    round_.updated_by = admin_id
    round_.updated_at = _utcnow()
    await db.commit()
    await db.refresh(round_)
    return round_


# --- 상태 전이 ---------------------------------------------------------------


async def open_round(
    db: AsyncSession, round_: GameRound, admin_id: int
) -> GameRound:
    if round_.status == "closed":
        raise RoundConflict("이미 마감된 라운드는 다시 열 수 없습니다.")
    other = await get_open_round(db, round_.session_id)
    if other is not None and other.id != round_.id:
        raise RoundConflict(
            f"이미 열린 라운드(order={other.order_index})가 있습니다. 먼저 마감하세요."
        )
    round_.status = "open"
    round_.opened_at = _utcnow()
    round_.updated_by = admin_id
    round_.updated_at = _utcnow()
    await db.commit()
    await db.refresh(round_)
    return round_


async def close_round(
    db: AsyncSession, round_: GameRound, admin_id: int | None
) -> GameRound:
    if round_.status != "open":
        raise RoundConflict("열려 있는(open) 라운드만 마감할 수 있습니다.")
    round_.status = "closed"
    round_.closed_at = _utcnow()
    round_.updated_by = admin_id
    round_.updated_at = _utcnow()
    await db.commit()
    await db.refresh(round_)
    return round_


# --- 제출 -------------------------------------------------------------------


async def submit_answer(
    db: AsyncSession, round_: GameRound, user_id: int, answer: str
) -> RoundSubmission:
    """button/vote 타입 1인 1답 제출. 중복 제출/마감 시 RoundConflict."""
    if round_.status != "open":
        raise RoundConflict("진행 중인 라운드가 아닙니다.")

    submission = RoundSubmission(
        round_id=round_.id,
        user_id=user_id,
        answer=answer,
        is_correct=_judge(round_.correct_answer, answer),
        server_time=_utcnow(),
    )
    db.add(submission)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise RoundConflict("이미 이 라운드에 제출했습니다.") from exc
    await db.refresh(submission)
    return submission


async def record_chat(
    db: AsyncSession,
    session_id: int,
    round_: GameRound | None,
    user_id: int,
    message: str,
) -> GameChatLog:
    """chat 타입 채팅 1건 기록. round_ 가 있으면 정답 판정까지 한다."""
    log = GameChatLog(
        session_id=session_id,
        round_id=round_.id if round_ else None,
        user_id=user_id,
        message=message,
        is_correct=_judge(round_.correct_answer, message) if round_ else False,
        server_time=_utcnow(),
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def round_distribution(
    db: AsyncSession, round_id: int
) -> tuple[int, dict[str, int]]:
    """라운드 제출 분포 (answer -> 개수)와 총 제출 수."""
    result = await db.execute(
        select(RoundSubmission.answer, func.count())
        .where(RoundSubmission.round_id == round_id)
        .group_by(RoundSubmission.answer)
    )
    dist = {answer: int(count) for answer, count in result.all()}
    return sum(dist.values()), dist


# --- tap 게임 전용 -----------------------------------------------------------


async def record_tap_count(
    db: AsyncSession, round_: GameRound, user_id: int
) -> TapLog:
    """count 모드: 탭 1회를 TapLog에 기록."""
    if round_.status != "open":
        raise RoundConflict("진행 중인 라운드가 아닙니다.")
    log = TapLog(round_id=round_.id, user_id=user_id, server_time=_utcnow())
    db.add(log)
    await db.commit()
    return log


async def record_tap_once(
    db: AsyncSession, round_: GameRound, user_id: int, value: str
) -> RoundSubmission:
    """speed/timing 모드: 1인 1회 제출 (RoundSubmission 재사용). 중복 시 무시."""
    if round_.status != "open":
        raise RoundConflict("진행 중인 라운드가 아닙니다.")
    submission = RoundSubmission(
        round_id=round_.id,
        user_id=user_id,
        answer=value,
        is_correct=False,
        server_time=_utcnow(),
    )
    db.add(submission)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise RoundConflict("이미 제출했습니다.")
    await db.refresh(submission)
    return submission


async def get_tap_results(db: AsyncSession, round_: GameRound) -> list[TapResult]:
    """모드별 결과 집계 및 순위 반환."""
    if round_.tap_mode == "count":
        return await _tap_count_results(db, round_)
    if round_.tap_mode == "speed":
        return await _tap_speed_results(db, round_)
    if round_.tap_mode == "timing":
        return await _tap_timing_results(db, round_)
    return []


async def _user_info(db: AsyncSession, round_: GameRound) -> dict[int, dict]:
    """세션 참가자의 nickname / team_name 조회."""
    stmt = (
        select(
            User.id,
            User.nickname,
            Team.name.label("team_name"),
        )
        .join(GameSession, GameSession.id == round_.session_id)
        .join(Timetable, Timetable.id == GameSession.timetable_id)
        .outerjoin(
            TeamMembership,
            and_(
                TeamMembership.season_id == Timetable.season_id,
                TeamMembership.user_id == User.id,
            ),
        )
        .outerjoin(Team, Team.id == TeamMembership.team_id)
        .where(GameSession.id == round_.session_id)
    )
    rows = (await db.execute(stmt)).all()
    return {r.id: {"nickname": r.nickname, "team_name": r.team_name} for r in rows}


async def _tap_count_results(db: AsyncSession, round_: GameRound) -> list[TapResult]:
    rows = await db.execute(
        select(TapLog.user_id, func.count().label("cnt"))
        .where(TapLog.round_id == round_.id)
        .group_by(TapLog.user_id)
        .order_by(func.count().desc())
    )
    items = list(rows.all())
    info = await _user_info(db, round_)
    results = []
    for rank, (user_id, cnt) in enumerate(items, start=1):
        u = info.get(user_id, {"nickname": f"user#{user_id}", "team_name": None})
        results.append(TapResult(user_id=user_id, nickname=u["nickname"],
                                 team_name=u["team_name"], value=float(cnt), rank=rank))
    return results


async def _tap_speed_results(db: AsyncSession, round_: GameRound) -> list[TapResult]:
    rows = await db.execute(
        select(RoundSubmission.user_id, RoundSubmission.answer)
        .where(RoundSubmission.round_id == round_.id)
        .order_by(RoundSubmission.server_time)
    )
    items = list(rows.all())
    info = await _user_info(db, round_)
    results = []
    for rank, (user_id, answer) in enumerate(items, start=1):
        u = info.get(user_id, {"nickname": f"user#{user_id}", "team_name": None})
        try:
            ms = float(answer)
        except (ValueError, TypeError):
            ms = 0.0
        results.append(TapResult(user_id=user_id, nickname=u["nickname"],
                                 team_name=u["team_name"], value=ms, rank=rank))
    return results


async def _tap_timing_results(db: AsyncSession, round_: GameRound) -> list[TapResult]:
    target = round_.target_time or 0.0
    rows = await db.execute(
        select(RoundSubmission.user_id, RoundSubmission.answer)
        .where(RoundSubmission.round_id == round_.id)
    )
    items = list(rows.all())
    info = await _user_info(db, round_)
    scored = []
    for user_id, answer in items:
        try:
            elapsed = float(answer)
        except (ValueError, TypeError):
            elapsed = 0.0
        diff = round(abs(elapsed - target), 1)
        scored.append((user_id, diff))
    scored.sort(key=lambda x: x[1])
    results = []
    for rank, (user_id, diff) in enumerate(scored, start=1):
        u = info.get(user_id, {"nickname": f"user#{user_id}", "team_name": None})
        results.append(TapResult(user_id=user_id, nickname=u["nickname"],
                                 team_name=u["team_name"], value=diff, rank=rank))
    return results


async def _auto_close_tap_round(round_id: int, delay: int) -> None:
    """count 모드 자동 마감: delay 초 후 라운드를 닫고 결과를 브로드캐스트."""
    await asyncio.sleep(delay)
    from app.websocket.events import broadcast_round_revealed, broadcast_tap_closed

    async with AsyncSessionLocal() as db:
        round_ = await get_round(db, round_id)
        if round_ is None or round_.status != "open":
            return
        await close_round(db, round_, admin_id=None)
        results = await get_tap_results(db, round_)
        await broadcast_tap_closed(round_, results)
        # button 타입과 동일하게 round_revealed 도 전송해 GameDetail 새로고침 트리거
        total, dist = await round_distribution(db, round_id)
        await broadcast_round_revealed(round_, total, dist)


async def _tap_count_snapshot(
    db: AsyncSession, round_: GameRound
) -> list[dict]:
    """count 모드 진행 중 누적: user_id별 탭 수 + 닉네임/팀."""
    rows = await db.execute(
        select(TapLog.user_id, func.count().label("cnt"))
        .where(TapLog.round_id == round_.id)
        .group_by(TapLog.user_id)
        .order_by(func.count().desc())
    )
    items = list(rows.all())
    if not items:
        return []
    info = await _user_info(db, round_)
    snapshot = []
    for user_id, cnt in items:
        u = info.get(user_id, {"nickname": f"user#{user_id}", "team_name": None})
        snapshot.append({
            "user_id": user_id,
            "nickname": u["nickname"],
            "team_name": u["team_name"],
            "count": int(cnt),
        })
    return snapshot


async def _tap_progress_loop(round_id: int, session_id: int, duration: int) -> None:
    """count 모드: duration 초 동안 0.5초마다 운영자에게 카운트 broadcast."""
    from app.websocket.events import broadcast_tap_progress

    end_at = asyncio.get_event_loop().time() + duration
    while asyncio.get_event_loop().time() < end_at:
        await asyncio.sleep(0.5)
        async with AsyncSessionLocal() as db:
            round_ = await get_round(db, round_id)
            if round_ is None or round_.status != "open":
                return
            counts = await _tap_count_snapshot(db, round_)
        await broadcast_tap_progress(session_id, round_id, counts)


async def _send_tap_signal(round_id: int) -> None:
    """speed 모드: 1~3초 랜덤 딜레이 후 signal_at 저장 + 브로드캐스트."""
    delay = random.uniform(1.0, 3.0)
    await asyncio.sleep(delay)
    from app.websocket.events import broadcast_tap_signal

    async with AsyncSessionLocal() as db:
        round_ = await get_round(db, round_id)
        if round_ is None or round_.status != "open":
            return
        round_.signal_at = _utcnow()
        round_.updated_at = _utcnow()
        await db.commit()
        await db.refresh(round_)
        await broadcast_tap_signal(round_)
