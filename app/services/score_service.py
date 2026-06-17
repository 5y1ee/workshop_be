"""점수 기록 비즈니스 로직."""

from datetime import datetime, timezone

from sqlalchemy import and_, case, func, or_, select, update
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


class ScoringNotAllowed(Exception):
    """현재 게임 상태에서는 점수를 기록/수정할 수 없다."""


# 신규 점수 기록이 허용되는 상태 (게임이 진행 중인 동안)
CREATABLE_STATES: frozenset[str] = frozenset({"in_progress", "scoring", "reward"})
# 기존 점수 수정(정정)이 허용되는 상태 — 종료(done) 후에도 정정 가능
EDITABLE_STATES: frozenset[str] = CREATABLE_STATES | {"done"}

# 개인 점수가 소속 팀 점수로 합산되는 게임 유형 (팀 대항전).
# 그 외 유형(individual, team_internal)의 개인 점수는 개인 전용으로만 집계한다.
TEAM_SCORED_TYPES: frozenset[str] = frozenset({"team_vs", "representative"})


async def _require_scoreable_state(
    db: AsyncSession, session_id: int, *, for_update: bool = False
) -> None:
    """세션이 점수를 매길/정정할 수 있는 상태인지 검증한다.

    신규 기록(for_update=False)은 in_progress/scoring/reward 에서만 허용하고,
    기존 점수 정정(for_update=True)은 종료(done) 후에도 허용한다.
    """
    allowed = EDITABLE_STATES if for_update else CREATABLE_STATES
    state = await db.scalar(
        select(GameSession.state).where(GameSession.id == session_id)
    )
    if state is None:
        raise InvalidScoreTarget("게임 세션을 찾을 수 없습니다.")
    if state not in allowed:
        action = "수정" if for_update else "기록"
        raise ScoringNotAllowed(
            f"현재 상태('{state}')에서는 점수를 {action}할 수 없습니다. "
            f"가능한 상태: {sorted(allowed)}"
        )


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


def _effective_participant_type(score_mode: str | None, participant_type: str) -> str:
    """타임테이블의 score_mode 오버라이드를 반영한 집계 단위.

    score_mode='team' → 팀 집계(team_vs와 동일), 'individual' → 개인 집계.
    NULL이면 게임의 participant_type을 그대로 쓴다.
    """
    if score_mode == "team":
        return "team_vs"
    if score_mode == "individual":
        return "individual"
    return participant_type


async def _session_game_context(
    db: AsyncSession, session_id: int
) -> tuple[str, int] | None:
    result = await db.execute(
        select(Game.participant_type, Timetable.season_id, Timetable.score_mode)
        .join(Timetable, Timetable.game_id == Game.id)
        .join(GameSession, GameSession.timetable_id == Timetable.id)
        .where(GameSession.id == session_id)
    )
    row = result.one_or_none()
    if row is None:
        return None
    return (
        _effective_participant_type(row.score_mode, row.participant_type),
        row.season_id,
    )


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
    await _require_scoreable_state(db, session_id)
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
    team_name = (
        select(Team.name)
        .where(Team.id == GameScoreLog.subject_id)
        .scalar_subquery()
    )
    user_name = (
        select(User.nickname)
        .where(User.id == GameScoreLog.subject_id)
        .scalar_subquery()
    )
    subject_name = case(
        (GameScoreLog.subject_type == "team", team_name),
        else_=user_name,
    )
    result = await db.execute(
        select(
            GameScoreLog.id,
            GameScoreLog.session_id,
            GameScoreLog.subject_type,
            GameScoreLog.subject_id,
            subject_name.label("subject_name"),
            GameScoreLog.chat_log_id,
            GameScoreLog.score,
            GameScoreLog.memo,
            GameScoreLog.created_by,
            GameScoreLog.created_at,
            GameScoreLog.updated_at,
        )
        .where(GameScoreLog.session_id == session_id)
        .order_by(GameScoreLog.id)
    )
    return [dict(row._mapping) for row in result.all()]


async def get_score(db: AsyncSession, score_id: int) -> GameScoreLog | None:
    result = await db.execute(
        select(GameScoreLog).where(GameScoreLog.id == score_id)
    )
    return result.scalar_one_or_none()


async def update_score(
    db: AsyncSession, score: GameScoreLog, data: ScoreUpdate, admin_id: int
) -> GameScoreLog:
    await _require_scoreable_state(db, score.session_id, for_update=True)
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
    """세션 스코어보드. 게임 유형에 따라 팀 또는 개인 단위로 집계한다.

    팀 대항전(team_vs/representative)은 팀 행만 — team 직접 점수에 더해 같은
    세션에서 개인이 얻은 점수를 그 유저의 시즌 팀으로 귀속해 합산한다.
    개인전(individual/team_internal)은 개인 행만 반환한다.
    """
    context = await _session_game_context(db, session_id)
    if context is None:
        return []
    participant_type, season_id = context
    total = func.coalesce(func.sum(GameScoreLog.score), 0)

    if participant_type in TEAM_SCORED_TYPES:
        # 각 로그를 팀으로 귀속: team 점수는 자기 팀, user 점수는 시즌 소속 팀.
        attributed_team_id = case(
            (GameScoreLog.subject_type == "team", GameScoreLog.subject_id),
            else_=TeamMembership.team_id,
        )
        result = await db.execute(
            select(
                Team.id.label("subject_id"),
                Team.name.label("subject_name"),
                total.label("total_score"),
            )
            .select_from(GameScoreLog)
            .outerjoin(
                TeamMembership,
                and_(
                    GameScoreLog.subject_type == "user",
                    TeamMembership.user_id == GameScoreLog.subject_id,
                    TeamMembership.season_id == season_id,
                ),
            )
            .join(Team, Team.id == attributed_team_id)
            .where(GameScoreLog.session_id == session_id)
            .group_by(Team.id, Team.name)
            .order_by(total.desc())
        )
        return [
            {
                "subject_type": "team",
                "subject_id": row.subject_id,
                "subject_name": row.subject_name,
                "total_score": int(row.total_score),
            }
            for row in result.all()
        ]

    result = await db.execute(
        select(User.id, User.nickname, total.label("total_score"))
        .select_from(GameScoreLog)
        .join(
            User,
            and_(
                GameScoreLog.subject_type == "user",
                User.id == GameScoreLog.subject_id,
            ),
        )
        .where(GameScoreLog.session_id == session_id)
        .group_by(User.id, User.nickname)
        .order_by(total.desc())
    )
    return [
        {
            "subject_type": "user",
            "subject_id": row.id,
            "subject_name": row.nickname,
            "total_score": int(row.total_score),
        }
        for row in result.all()
    ]


async def season_scoreboard(db: AsyncSession, season_id: int) -> list[dict]:
    """시즌 전체 팀 누적 점수 (내림차순). 점수가 0인 팀도 포함한다.

    팀 총점 = team 직접 점수 + 팀 대항전(team_vs/representative) 세션에서 개인이
    얻은 점수를 그 유저의 시즌 팀으로 귀속한 합. 개인전 점수는 팀에 합산하지 않는다.
    """
    # 시즌 세션과 게임 유형(타임테이블 score_mode 오버라이드 반영)을 한 번에 묶는다.
    effective_type = case(
        (Timetable.score_mode == "team", "team_vs"),
        (Timetable.score_mode == "individual", "individual"),
        else_=Game.participant_type,
    )
    season_sessions = (
        select(
            GameSession.id.label("session_id"),
            effective_type.label("participant_type"),
        )
        .join(Timetable, GameSession.timetable_id == Timetable.id)
        .join(Game, Timetable.game_id == Game.id)
        .where(Timetable.season_id == season_id)
        .subquery()
    )
    # 시즌 내 각 점수 로그를 팀으로 귀속 (귀속 불가 시 NULL → 집계 제외).
    attributed = (
        select(
            case(
                (GameScoreLog.subject_type == "team", GameScoreLog.subject_id),
                else_=TeamMembership.team_id,
            ).label("team_id"),
            GameScoreLog.score.label("score"),
        )
        .select_from(GameScoreLog)
        .join(season_sessions, GameScoreLog.session_id == season_sessions.c.session_id)
        .outerjoin(
            TeamMembership,
            and_(
                GameScoreLog.subject_type == "user",
                TeamMembership.user_id == GameScoreLog.subject_id,
                TeamMembership.season_id == season_id,
            ),
        )
        .where(
            or_(
                GameScoreLog.subject_type == "team",
                and_(
                    GameScoreLog.subject_type == "user",
                    season_sessions.c.participant_type.in_(TEAM_SCORED_TYPES),
                ),
            )
        )
        .subquery()
    )
    total = func.coalesce(func.sum(attributed.c.score), 0)
    result = await db.execute(
        select(Team.id, Team.name, total.label("total_score"))
        .select_from(Team)
        .outerjoin(attributed, attributed.c.team_id == Team.id)
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


async def season_user_status(db: AsyncSession, season_id: int) -> list[dict]:
    """운영자용 전체 사용자 현황.

    cumulative_score 는 시즌 점수 로그 합계이고, point 는 뽑기 사용 후 남은 현재 포인트다.
    """
    season_session_ids = (
        select(GameSession.id)
        .join(Timetable, GameSession.timetable_id == Timetable.id)
        .where(Timetable.season_id == season_id)
        .scalar_subquery()
    )
    cumulative = (
        select(
            GameScoreLog.subject_id.label("user_id"),
            func.coalesce(func.sum(GameScoreLog.score), 0).label("cumulative_score"),
        )
        .where(
            GameScoreLog.subject_type == "user",
            GameScoreLog.session_id.in_(season_session_ids),
        )
        .group_by(GameScoreLog.subject_id)
        .subquery()
    )
    result = await db.execute(
        select(
            User.id.label("user_id"),
            User.nickname,
            User.role,
            Team.id.label("team_id"),
            Team.name.label("team_name"),
            func.coalesce(cumulative.c.cumulative_score, 0).label("cumulative_score"),
            User.point,
        )
        .select_from(User)
        .outerjoin(
            TeamMembership,
            and_(
                TeamMembership.user_id == User.id,
                TeamMembership.season_id == season_id,
            ),
        )
        .outerjoin(Team, Team.id == TeamMembership.team_id)
        .outerjoin(cumulative, cumulative.c.user_id == User.id)
        .order_by(User.role, User.id)
    )
    return [
        {
            "user_id": row.user_id,
            "nickname": row.nickname,
            "role": row.role,
            "team_id": row.team_id,
            "team_name": row.team_name,
            "cumulative_score": int(row.cumulative_score),
            "point": int(row.point),
        }
        for row in result.all()
    ]
