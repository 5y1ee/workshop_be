"""점수 기록 비즈니스 로직."""

from datetime import datetime, timezone

from sqlalchemy import and_, case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game
from app.models.game_session import GameChatLog, GameScoreLog, GameSession
from app.models.team import Team
from app.models.team_member import TeamMembership
from app.models.timetable import Timetable
from app.models.user import User
from app.schemas.score import ScoreCreate, ScoreUpdate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class InvalidChatScore(Exception):
    """정답 후보 채팅과 연결할 수 없는 점수 기록."""


class DuplicateChatScore(Exception):
    """이미 점수로 확정된 채팅 후보."""


class InvalidScoreTarget(Exception):
    """현재 세션/시즌에 점수를 줄 수 없는 대상."""


async def _apply_user_point_delta(
    db: AsyncSession, user_id: int, delta: int
) -> None:
    """개인 점수 로그 변동분을 users.point 누적값에 반영한다 (커밋은 호출부에서)."""
    if delta == 0:
        return
    await db.execute(
        update(User).where(User.id == user_id).values(point=User.point + delta)
    )


async def subject_exists(db: AsyncSession, subject_type: str, subject_id: int) -> bool:
    """subject_type 에 따라 teams 또는 users 에 해당 id 가 있는지 확인."""
    model = Team if subject_type == "team" else User
    result = await db.execute(select(model.id).where(model.id == subject_id))
    return result.scalar_one_or_none() is not None


async def _session_game_context(
    db: AsyncSession, session_id: int
) -> tuple[str, int] | None:
    result = await db.execute(
        select(Game.participant_type, Timetable.season_id)
        .join(Timetable, Timetable.game_id == Game.id)
        .join(GameSession, GameSession.timetable_id == Timetable.id)
        .where(GameSession.id == session_id)
    )
    row = result.one_or_none()
    if row is None:
        return None
    return row.participant_type, row.season_id


async def _validate_score_target(
    db: AsyncSession, session_id: int, data: ScoreCreate
) -> None:
    context = await _session_game_context(db, session_id)
    if context is None:
        raise InvalidScoreTarget("게임 세션을 찾을 수 없습니다.")

    _, season_id = context

    if data.subject_type == "team":
        team_season_id = await db.scalar(
            select(Team.season_id).where(Team.id == data.subject_id)
        )
        if team_season_id != season_id:
            raise InvalidScoreTarget("현재 시즌의 팀에만 점수를 기록할 수 있습니다.")
        return

    exists_in_season = await db.scalar(
        select(TeamMembership.id).where(
            TeamMembership.season_id == season_id,
            TeamMembership.user_id == data.subject_id,
        )
    )
    if exists_in_season is None:
        raise InvalidScoreTarget("현재 시즌에 배정된 유저에게만 점수를 기록할 수 있습니다.")


async def create_score(
    db: AsyncSession, session_id: int, data: ScoreCreate, admin_id: int
) -> GameScoreLog:
    await _validate_score_target(db, session_id, data)

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
    if data.subject_type == "user":
        await _apply_user_point_delta(db, data.subject_id, data.score)
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
    old_score = score.score
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(score, key, value)
    score.updated_by = admin_id
    score.updated_at = _utcnow()
    if score.subject_type == "user" and score.score != old_score:
        await _apply_user_point_delta(db, score.subject_id, score.score - old_score)
    await db.commit()
    await db.refresh(score)
    return score


async def score_summary(db: AsyncSession, session_id: int) -> list[dict]:
    """세션 내 subject 별 합산 점수 (내림차순)."""
    total = func.coalesce(func.sum(GameScoreLog.score), 0)
    subject_name = case(
        (GameScoreLog.subject_type == "team", Team.name),
        else_=User.nickname,
    )
    result = await db.execute(
        select(
            GameScoreLog.subject_type,
            GameScoreLog.subject_id,
            subject_name.label("subject_name"),
            total.label("total_score"),
        )
        .outerjoin(
            Team,
            and_(
                GameScoreLog.subject_type == "team",
                GameScoreLog.subject_id == Team.id,
            ),
        )
        .outerjoin(
            User,
            and_(
                GameScoreLog.subject_type == "user",
                GameScoreLog.subject_id == User.id,
            ),
        )
        .where(GameScoreLog.session_id == session_id)
        .group_by(GameScoreLog.subject_type, GameScoreLog.subject_id, Team.name, User.nickname)
        .order_by(total.desc())
    )
    return [
        {
            "subject_type": row.subject_type,
            "subject_id": row.subject_id,
            "subject_name": row.subject_name,
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


async def season_user_scoreboard(db: AsyncSession, season_id: int) -> list[dict]:
    """시즌 전체 개인 누적 점수 (내림차순). 점수가 0인 배정 유저도 포함한다."""
    season_session_ids = (
        select(GameSession.id)
        .join(Timetable, GameSession.timetable_id == Timetable.id)
        .where(Timetable.season_id == season_id)
        .scalar_subquery()
    )
    total = func.coalesce(func.sum(GameScoreLog.score), 0)
    result = await db.execute(
        select(User.id, User.nickname, total.label("total_score"))
        .select_from(User)
        .join(
            TeamMembership,
            and_(
                TeamMembership.user_id == User.id,
                TeamMembership.season_id == season_id,
            ),
        )
        .outerjoin(
            GameScoreLog,
            and_(
                GameScoreLog.subject_type == "user",
                GameScoreLog.subject_id == User.id,
                GameScoreLog.session_id.in_(season_session_ids),
            ),
        )
        .group_by(User.id, User.nickname)
        .order_by(total.desc(), User.id)
    )
    return [
        {
            "user_id": row.id,
            "name": row.nickname,
            "total_score": int(row.total_score),
        }
        for row in result.all()
    ]
