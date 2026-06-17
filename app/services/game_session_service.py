"""게임 세션 상태 머신.

상태 흐름: idle → ready → in_progress → scoring → reward → done
(보상 단계가 없는 게임은 scoring → done 으로 바로 종료 가능)
"""

import secrets
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game_session import GameSession
from app.models.buff import TeamBuff

# 허용된 상태 전이 맵 (forward-only)
TRANSITIONS: dict[str, set[str]] = {
    "idle": {"ready"},
    "ready": {"in_progress"},
    "in_progress": {"scoring"},
    "scoring": {"reward", "done"},
    "reward": {"done"},
    "done": set(),
}


class InvalidStateTransition(Exception):
    """허용되지 않은 상태 전이 시도."""

    def __init__(self, from_state: str, to_state: str) -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.allowed = sorted(TRANSITIONS.get(from_state, set()))
        super().__init__(
            f"'{from_state}' → '{to_state}' 전이는 허용되지 않습니다. "
            f"가능한 전이: {self.allowed or '없음 (종료 상태)'}"
        )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create_session(db: AsyncSession, timetable_id: int) -> GameSession:
    session = GameSession(timetable_id=timetable_id, state="idle")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: int) -> GameSession | None:
    result = await db.execute(select(GameSession).where(GameSession.id == session_id))
    return result.scalar_one_or_none()


async def list_sessions_for_timetable(
    db: AsyncSession, timetable_id: int
) -> list[GameSession]:
    result = await db.execute(
        select(GameSession)
        .where(GameSession.timetable_id == timetable_id)
        .order_by(GameSession.id)
    )
    return list(result.scalars().all())


async def transition(
    db: AsyncSession, session: GameSession, to_state: str, admin_id: int
) -> GameSession:
    if to_state not in TRANSITIONS.get(session.state, set()):
        raise InvalidStateTransition(session.state, to_state)

    # 부수효과
    if to_state == "in_progress":
        if session.started_at is None:
            session.started_at = _utcnow()
        if session.seed is None:
            # 룰렛/도박 결과 생성을 위한 서버 시드 (공정성용, 외부 비노출)
            session.seed = secrets.token_hex(16)
    elif to_state == "ready":
        await db.execute(
            update(TeamBuff)
            .where(
                TeamBuff.session_id == session.id,
                TeamBuff.activated_at.is_(None),
            )
            .values(activated_at=_utcnow())
        )
    elif to_state == "done":
        session.ended_at = _utcnow()

    session.state = to_state
    session.updated_by = admin_id
    session.updated_at = _utcnow()
    await db.commit()
    await db.refresh(session)
    return session
