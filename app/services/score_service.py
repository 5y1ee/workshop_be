"""점수 기록 비즈니스 로직."""

from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game_session import GameChatLog, GameScoreLog, GameSession
from app.models.team import Team
from app.models.timetable import Timetable
from app.models.user import User
from app.schemas.score import ScoreCreate, ScoreUpdate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class InvalidChatScore(Exception):
    """정답 후보 채팅과 연결할 수 없는 점수 기록."""


class DuplicateChatScore(Exception):
    """이미 점수로 확정된 채팅 후보."""


async def subject_exists(db: AsyncSession, subject_type: str, subject_id: int) -> bool:
    """subject_type 에 따라 teams 또는 users 에 해당 id 가 있는지 확인."""
    model = Team if subject_type == "team" else User
    result = await db.execute(select(model.id).where(model.id == subject_id))
    return result.scalar_one_or_none() is not None


async def create_score(
    db: AsyncSession, session_id: int, data: ScoreCreate, admin_id: int
) -> GameScoreLog:
    if data.chat_log_id is not None:
        chat = await db.get(GameChatLog, data.chat_log_id)
        if chat is None or chat.session_id != session_id:
            raise InvalidChatScore("현재 세션의 채팅 후보가 아닙니다.")
        if not chat.is_correct:
            raise InvalidChatScore("정답 후보만 점수로 기록할 수 있습니다.")
        existing = await db.execute(
            select(GameScoreLog.id).where(GameScoreLog.chat_log_id == data.chat_log_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise DuplicateChatScore("이미 점수로 기록된 정답 후보입니다.")

    score = GameScoreLog(
        session_id=session_id,
        subject_type=data.subject_type,
        subject_id=data.subject_id,
        chat_log_id=data.chat_log_id,
        score=data.score,
        memo=data.memo,
        created_by=admin_id,
    )
    db.add(score)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if data.chat_log_id is not None:
            raise DuplicateChatScore("이미 점수로 기록된 정답 후보입니다.") from exc
        raise
    await db.refresh(score)
    return score


async def list_scores(db: AsyncSession, session_id: int) -> list[GameScoreLog]:
    result = await db.execute(
        select(GameScoreLog)
        .where(GameScoreLog.session_id == session_id)
        .order_by(GameScoreLog.id)
    )
    return list(result.scalars().all())


async def get_score(db: AsyncSession, score_id: int) -> GameScoreLog | None:
    result = await db.execute(
        select(GameScoreLog).where(GameScoreLog.id == score_id)
    )
    return result.scalar_one_or_none()


async def update_score(
    db: AsyncSession, score: GameScoreLog, data: ScoreUpdate, admin_id: int
) -> GameScoreLog:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(score, key, value)
    score.updated_by = admin_id
    score.updated_at = _utcnow()
    await db.commit()
    await db.refresh(score)
    return score


async def score_summary(db: AsyncSession, session_id: int) -> list[dict]:
    """세션 내 subject 별 합산 점수 (내림차순)."""
    total = func.coalesce(func.sum(GameScoreLog.score), 0)
    result = await db.execute(
        select(
            GameScoreLog.subject_type,
            GameScoreLog.subject_id,
            total.label("total_score"),
        )
        .where(GameScoreLog.session_id == session_id)
        .group_by(GameScoreLog.subject_type, GameScoreLog.subject_id)
        .order_by(total.desc())
    )
    return [
        {
            "subject_type": row.subject_type,
            "subject_id": row.subject_id,
            "total_score": int(row.total_score),
        }
        for row in result.all()
    ]


async def season_scoreboard(db: AsyncSession, season_id: int) -> list[dict]:
    """시즌 전체 팀 누적 점수 (내림차순). 점수가 0인 팀도 포함한다.

    game_score_logs → game_sessions → timetable 경로로 시즌에 속한 세션의
    team 점수를 합산한다.
    """
    season_session_ids = (
        select(GameSession.id)
        .join(Timetable, GameSession.timetable_id == Timetable.id)
        .where(Timetable.season_id == season_id)
        .scalar_subquery()
    )
    total = func.coalesce(func.sum(GameScoreLog.score), 0)
    result = await db.execute(
        select(Team.id, Team.name, total.label("total_score"))
        .select_from(Team)
        .outerjoin(
            GameScoreLog,
            and_(
                GameScoreLog.subject_type == "team",
                GameScoreLog.subject_id == Team.id,
                GameScoreLog.session_id.in_(season_session_ids),
            ),
        )
        .where(Team.season_id == season_id)
        .group_by(Team.id, Team.name)
        .order_by(total.desc(), Team.id)
    )
    return [
        {
            "team_id": row.id,
            "name": row.name,
            "total_score": int(row.total_score),
        }
        for row in result.all()
    ]
