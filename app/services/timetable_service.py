"""타임테이블(시즌 진행표) 비즈니스 로직."""

from datetime import datetime, timezone

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.buff import TeamBuff
from app.models.envelope import Envelope
from app.models.game_round import GameRound, RoundSubmission, TapLog
from app.models.game_session import GameSession
from app.models.game_session import GameChatLog, GameResult, GameScoreLog
from app.models.raffle import RaffleTicket
from app.models.timetable import Timetable
from app.schemas.timetable import TimetableCreate, TimetableUpdate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create_entry(
    db: AsyncSession, season_id: int, data: TimetableCreate
) -> Timetable:
    entry = Timetable(season_id=season_id, **data.model_dump())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_entries(db: AsyncSession, season_id: int) -> list[Timetable]:
    result = await db.execute(
        select(Timetable)
        .where(Timetable.season_id == season_id)
        .order_by(Timetable.order_index, Timetable.id)
    )
    return list(result.scalars().all())


async def get_entry(db: AsyncSession, entry_id: int) -> Timetable | None:
    result = await db.execute(select(Timetable).where(Timetable.id == entry_id))
    return result.scalar_one_or_none()


async def update_entry(
    db: AsyncSession, entry: Timetable, data: TimetableUpdate, admin_id: int
) -> Timetable:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    entry.updated_by = admin_id
    entry.updated_at = _utcnow()
    await db.commit()
    await db.refresh(entry)
    return entry


class TimetableDeleteBlocked(Exception):
    """이미 진행되었거나 기록이 있는 타임테이블 항목은 삭제할 수 없음."""


async def delete_entry(db: AsyncSession, entry: Timetable) -> None:
    sessions = list(
        (
            await db.execute(
                select(GameSession).where(GameSession.timetable_id == entry.id)
            )
        ).scalars().all()
    )
    session_ids = [session.id for session in sessions]

    if await _has_started_or_recorded_session(db, sessions, session_ids):
        raise TimetableDeleteBlocked(
            "이미 진행되었거나 기록이 있는 게임은 타임테이블에서 삭제할 수 없습니다."
        )

    season_id = entry.season_id
    order_index = entry.order_index
    if session_ids:
        await db.execute(delete(GameRound).where(GameRound.session_id.in_(session_ids)))
        await db.execute(delete(GameSession).where(GameSession.id.in_(session_ids)))
    await db.delete(entry)
    await db.execute(
        update(Timetable)
        .where(Timetable.season_id == season_id, Timetable.order_index > order_index)
        .values(order_index=Timetable.order_index - 1)
    )
    await db.commit()


async def _has_started_or_recorded_session(
    db: AsyncSession, sessions: list[GameSession], session_ids: list[int]
) -> bool:
    if not session_ids:
        return False

    if any(
        session.state != "idle"
        or session.started_at is not None
        or session.ended_at is not None
        for session in sessions
    ):
        return True

    round_ids = select(GameRound.id).where(GameRound.session_id.in_(session_ids))
    checks = [
        select(GameScoreLog.id).where(GameScoreLog.session_id.in_(session_ids)).limit(1),
        select(GameResult.id).where(GameResult.session_id.in_(session_ids)).limit(1),
        select(GameChatLog.id).where(GameChatLog.session_id.in_(session_ids)).limit(1),
        select(Envelope.id).where(Envelope.session_id.in_(session_ids)).limit(1),
        select(RaffleTicket.id).where(RaffleTicket.session_id.in_(session_ids)).limit(1),
        select(TeamBuff.id)
        .where(
            or_(
                TeamBuff.session_id.in_(session_ids),
                TeamBuff.expires_after.in_(session_ids),
            )
        )
        .limit(1),
        select(GameRound.id)
        .where(
            GameRound.session_id.in_(session_ids),
            or_(
                GameRound.status != "waiting",
                GameRound.opened_at.is_not(None),
                GameRound.closed_at.is_not(None),
                GameRound.signal_at.is_not(None),
            ),
        )
        .limit(1),
        select(RoundSubmission.id).where(RoundSubmission.round_id.in_(round_ids)).limit(1),
        select(TapLog.id).where(TapLog.round_id.in_(round_ids)).limit(1),
    ]
    for stmt in checks:
        if await db.scalar(stmt) is not None:
            return True
    return False
