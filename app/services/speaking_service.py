"""전역 발언권 이벤트 비즈니스 로직."""

import asyncio
import random
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.speaking import (
    SpeakingEvent,
    SpeakingGrant,
    SpeakingSubmission,
    SpeakingTapLog,
)
from app.models.team import Team
from app.models.team_member import TeamMembership
from app.models.user import User
from app.schemas.speaking import SpeakingEventCreate, SpeakingResult


class SpeakingConflict(Exception):
    """발언권 이벤트 상태/참여/지급 충돌."""


# speed 모드에서 신호 전에 누른 입력(부정출발)을 SpeakingSubmission.value 에 저장하는 센티넬.
_SPEAKING_DQ = -1.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create_event(
    db: AsyncSession, season_id: int, data: SpeakingEventCreate, admin_id: int
) -> SpeakingEvent:
    if await get_current_event(db, season_id) is not None:
        raise SpeakingConflict("이미 진행 중인 발언권 이벤트가 있습니다.")

    duration = data.duration
    target_time = data.target_time
    if data.mode == "count":
        duration = duration or 10
        if duration < 1:
            raise SpeakingConflict("제한 시간은 1초 이상이어야 합니다.")
        target_time = None
    elif data.mode == "timing":
        target_time = target_time or 7.5
        if target_time <= 0:
            raise SpeakingConflict("목표 시간은 0보다 커야 합니다.")
        duration = None
    else:
        duration = None
        target_time = None

    event = SpeakingEvent(
        season_id=season_id,
        mode=data.mode,
        status="open",
        duration=duration,
        target_time=target_time,
        opened_at=_utcnow(),
        created_by=admin_id,
    )
    db.add(event)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise SpeakingConflict("이미 진행 중인 발언권 이벤트가 있습니다.") from exc
    await db.refresh(event)
    return event


async def get_event(db: AsyncSession, event_id: int) -> SpeakingEvent | None:
    result = await db.execute(select(SpeakingEvent).where(SpeakingEvent.id == event_id))
    return result.scalar_one_or_none()


async def get_current_event(
    db: AsyncSession, season_id: int
) -> SpeakingEvent | None:
    result = await db.execute(
        select(SpeakingEvent).where(
            SpeakingEvent.season_id == season_id,
            SpeakingEvent.status == "open",
        )
    )
    return result.scalar_one_or_none()


async def close_event(
    db: AsyncSession, event: SpeakingEvent, admin_id: int | None
) -> SpeakingEvent:
    if event.status != "open":
        raise SpeakingConflict("진행 중인 발언권 이벤트가 아닙니다.")
    event.status = "closed"
    event.closed_at = _utcnow()
    event.updated_by = admin_id
    event.updated_at = _utcnow()
    await db.commit()
    await db.refresh(event)
    return event


async def _require_member(
    db: AsyncSession, event: SpeakingEvent, user_id: int
) -> None:
    exists = await db.scalar(
        select(TeamMembership.id).where(
            TeamMembership.season_id == event.season_id,
            TeamMembership.user_id == user_id,
        )
    )
    if exists is None:
        raise SpeakingConflict("선택 시즌에 배정된 유저만 참여할 수 있습니다.")


async def record_count(
    db: AsyncSession, event: SpeakingEvent, user_id: int
) -> SpeakingTapLog:
    if event.status != "open" or event.mode != "count":
        raise SpeakingConflict("진행 중인 횟수 대결이 아닙니다.")
    await _require_member(db, event, user_id)
    log = SpeakingTapLog(event_id=event.id, user_id=user_id, server_time=_utcnow())
    db.add(log)
    await db.commit()
    return log


async def record_once(
    db: AsyncSession, event: SpeakingEvent, user_id: int, value: float
) -> SpeakingSubmission:
    if event.status != "open" or event.mode not in ("speed", "timing"):
        raise SpeakingConflict("진행 중인 제출형 발언권 이벤트가 아닙니다.")
    if value < 0:
        raise SpeakingConflict("기록 값은 0 이상이어야 합니다.")
    await _require_member(db, event, user_id)
    submission = SpeakingSubmission(
        event_id=event.id,
        user_id=user_id,
        value=value,
        server_time=_utcnow(),
    )
    db.add(submission)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise SpeakingConflict("이미 제출했습니다.") from exc
    await db.refresh(submission)
    return submission


async def record_disqualify(
    db: AsyncSession, event: SpeakingEvent, user_id: int
) -> SpeakingSubmission:
    """speed 모드: 신호 전에 누른 부정출발을 실격(DQ)으로 1회 기록.

    SpeakingSubmission 유니크 제약을 재사용해 멱등 처리하며, 한 번 실격되면
    이후 정상 제출도 차단된다.
    """
    if event.status != "open" or event.mode != "speed":
        raise SpeakingConflict("진행 중인 빠르기 대결이 아닙니다.")
    await _require_member(db, event, user_id)
    submission = SpeakingSubmission(
        event_id=event.id,
        user_id=user_id,
        value=_SPEAKING_DQ,
        server_time=_utcnow(),
    )
    db.add(submission)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise SpeakingConflict("이미 제출했습니다.") from exc
    await db.refresh(submission)
    return submission


async def _user_info(db: AsyncSession, season_id: int) -> dict[int, dict]:
    rows = await db.execute(
        select(
            User.id,
            User.nickname,
            Team.id.label("team_id"),
            Team.name.label("team_name"),
        )
        .join(TeamMembership, TeamMembership.user_id == User.id)
        .outerjoin(Team, Team.id == TeamMembership.team_id)
        .where(TeamMembership.season_id == season_id)
    )
    return {
        row.id: {
            "nickname": row.nickname,
            "team_id": row.team_id,
            "team_name": row.team_name,
        }
        for row in rows.all()
    }


async def user_info_for_event(
    db: AsyncSession, event: SpeakingEvent, user_id: int
) -> dict:
    info = await _user_info(db, event.season_id)
    return info.get(
        user_id,
        {"nickname": f"user#{user_id}", "team_id": None, "team_name": None},
    )


async def get_count_snapshot(
    db: AsyncSession, event: SpeakingEvent
) -> list[dict]:
    rows = await db.execute(
        select(SpeakingTapLog.user_id, func.count().label("cnt"))
        .where(SpeakingTapLog.event_id == event.id)
        .group_by(SpeakingTapLog.user_id)
        .order_by(func.count().desc(), SpeakingTapLog.user_id)
    )
    items = list(rows.all())
    if not items:
        return []
    info = await _user_info(db, event.season_id)
    return [
        {
            "user_id": user_id,
            "nickname": info.get(user_id, {}).get("nickname", f"user#{user_id}"),
            "team_name": info.get(user_id, {}).get("team_name"),
            "count": int(cnt),
        }
        for user_id, cnt in items
    ]


async def get_results(
    db: AsyncSession, event: SpeakingEvent
) -> list[SpeakingResult]:
    if event.mode == "count":
        results = await _count_results(db, event)
    elif event.mode == "speed":
        results = await _speed_results(db, event)
    elif event.mode == "timing":
        results = await _timing_results(db, event)
    else:
        results = []

    granted_rows = await db.execute(
        select(SpeakingGrant.user_id).where(SpeakingGrant.event_id == event.id)
    )
    granted_ids = {row.user_id for row in granted_rows.all()}
    return [r.model_copy(update={"granted": r.user_id in granted_ids}) for r in results]


async def _count_results(
    db: AsyncSession, event: SpeakingEvent
) -> list[SpeakingResult]:
    rows = await db.execute(
        select(SpeakingTapLog.user_id, func.count().label("cnt"))
        .where(SpeakingTapLog.event_id == event.id)
        .group_by(SpeakingTapLog.user_id)
        .order_by(func.count().desc(), SpeakingTapLog.user_id)
    )
    info = await _user_info(db, event.season_id)
    results: list[SpeakingResult] = []
    for rank, (user_id, cnt) in enumerate(rows.all(), start=1):
        u = info.get(
            user_id,
            {"nickname": f"user#{user_id}", "team_id": None, "team_name": None},
        )
        results.append(
            SpeakingResult(
                user_id=user_id,
                nickname=u["nickname"],
                team_id=u["team_id"],
                team_name=u["team_name"],
                value=float(cnt),
                rank=rank,
            )
        )
    return results


async def _speed_results(
    db: AsyncSession, event: SpeakingEvent
) -> list[SpeakingResult]:
    rows = await db.execute(
        select(
            SpeakingSubmission.user_id,
            SpeakingSubmission.value,
            SpeakingSubmission.server_time,
        )
        .where(SpeakingSubmission.event_id == event.id)
        .order_by(SpeakingSubmission.value, SpeakingSubmission.server_time)
    )
    info = await _user_info(db, event.season_id)
    items = list(rows.all())
    # 신호 전 입력으로 실격(DQ)된 제출은 순위에서 제외하고 뒤로 보낸다.
    valid = [(uid, val) for uid, val, _st in items if val != _SPEAKING_DQ]
    disqualified = [uid for uid, val, _st in items if val == _SPEAKING_DQ]

    def _info(user_id: int) -> dict:
        return info.get(
            user_id,
            {"nickname": f"user#{user_id}", "team_id": None, "team_name": None},
        )

    results: list[SpeakingResult] = []
    rank = 0
    for user_id, value in valid:
        rank += 1
        u = _info(user_id)
        results.append(
            SpeakingResult(
                user_id=user_id,
                nickname=u["nickname"],
                team_id=u["team_id"],
                team_name=u["team_name"],
                value=float(value),
                rank=rank,
            )
        )
    for user_id in disqualified:
        rank += 1
        u = _info(user_id)
        results.append(
            SpeakingResult(
                user_id=user_id,
                nickname=u["nickname"],
                team_id=u["team_id"],
                team_name=u["team_name"],
                value=0.0,
                rank=rank,
                disqualified=True,
            )
        )
    return results


async def _timing_results(
    db: AsyncSession, event: SpeakingEvent
) -> list[SpeakingResult]:
    target = event.target_time or 0.0
    rows = await db.execute(
        select(SpeakingSubmission.user_id, SpeakingSubmission.value).where(
            SpeakingSubmission.event_id == event.id
        )
    )
    scored = [
        (user_id, round(abs(float(value) - target), 1))
        for user_id, value in rows.all()
    ]
    scored.sort(key=lambda row: (row[1], row[0]))
    info = await _user_info(db, event.season_id)
    results: list[SpeakingResult] = []
    for rank, (user_id, diff) in enumerate(scored, start=1):
        u = info.get(
            user_id,
            {"nickname": f"user#{user_id}", "team_id": None, "team_name": None},
        )
        results.append(
            SpeakingResult(
                user_id=user_id,
                nickname=u["nickname"],
                team_id=u["team_id"],
                team_name=u["team_name"],
                value=diff,
                rank=rank,
            )
        )
    return results


async def grant_speaking_right(
    db: AsyncSession, event: SpeakingEvent, user_id: int, admin_id: int
) -> tuple[SpeakingGrant, SpeakingResult]:
    if event.status != "closed":
        raise SpeakingConflict("마감된 발언권 이벤트에서만 발언권을 부여할 수 있습니다.")
    result = next((r for r in await get_results(db, event) if r.user_id == user_id), None)
    if result is None:
        raise SpeakingConflict("결과에 없는 유저에게 발언권을 부여할 수 없습니다.")
    if result.disqualified:
        raise SpeakingConflict("실격한 유저에게는 발언권을 부여할 수 없습니다.")

    grant = SpeakingGrant(
        event_id=event.id,
        user_id=user_id,
        rank=result.rank,
        value=result.value,
        granted_by=admin_id,
        granted_at=_utcnow(),
    )
    db.add(grant)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise SpeakingConflict("이미 발언권을 부여한 유저입니다.") from exc
    await db.refresh(grant)
    return grant, result.model_copy(update={"granted": True})


async def auto_close_count_event(event_id: int, delay: int) -> None:
    await asyncio.sleep(delay)
    from app.websocket.events import broadcast_speaking_event_closed

    async with AsyncSessionLocal() as db:
        event = await get_event(db, event_id)
        if event is None or event.status != "open":
            return
        event = await close_event(db, event, admin_id=None)
        results = await get_results(db, event)
        await broadcast_speaking_event_closed(event, results)


async def speaking_progress_loop(event_id: int, duration: int) -> None:
    from app.websocket.events import broadcast_speaking_progress

    end_at = asyncio.get_event_loop().time() + duration
    while asyncio.get_event_loop().time() < end_at:
        await asyncio.sleep(0.5)
        async with AsyncSessionLocal() as db:
            event = await get_event(db, event_id)
            if event is None or event.status != "open":
                return
            counts = await get_count_snapshot(db, event)
        await broadcast_speaking_progress(event.season_id, event.id, counts)


async def send_signal_after_delay(event_id: int) -> None:
    delay = random.uniform(3.0, 5.0)
    await asyncio.sleep(delay)
    from app.websocket.events import broadcast_speaking_signal

    async with AsyncSessionLocal() as db:
        event = await get_event(db, event_id)
        if event is None or event.status != "open" or event.mode != "speed":
            return
        event.signal_at = _utcnow()
        event.updated_at = _utcnow()
        await db.commit()
        await db.refresh(event)
        await broadcast_speaking_signal(event)
