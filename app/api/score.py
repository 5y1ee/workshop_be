from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.score import (
    ScoreCreate,
    ScoreRead,
    ScoreSummaryItem,
    ScoreUpdate,
    TeamScoreboardItem,
)
from app.services import game_session_service, score_service
from app.websocket.events import broadcast_score_recorded

router = APIRouter(tags=["scores"])


async def _require_session(db: DbSession, session_id: int) -> None:
    if await game_session_service.get_session(db, session_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="게임 세션을 찾을 수 없습니다."
        )


async def _require_subject(db: DbSession, subject_type: str, subject_id: int) -> None:
    if not await score_service.subject_exists(db, subject_type, subject_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="존재하지 않는 대상(team/user)입니다.",
        )


@router.post(
    "/sessions/{session_id}/scores",
    response_model=ScoreRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_score(
    session_id: int, payload: ScoreCreate, db: DbSession, admin: AdminUser
) -> ScoreRead:
    await _require_session(db, session_id)
    await _require_subject(db, payload.subject_type, payload.subject_id)
    score = await score_service.create_score(db, session_id, payload, admin.id)
    await broadcast_score_recorded(score)
    return score


@router.get("/sessions/{session_id}/scores", response_model=list[ScoreRead])
async def list_scores(
    session_id: int, db: DbSession, user: CurrentUser
) -> list[ScoreRead]:
    return await score_service.list_scores(db, session_id)


@router.get(
    "/sessions/{session_id}/scores/summary",
    response_model=list[ScoreSummaryItem],
)
async def score_summary(
    session_id: int, db: DbSession, user: CurrentUser
) -> list[ScoreSummaryItem]:
    return await score_service.score_summary(db, session_id)


@router.get(
    "/seasons/{season_id}/scoreboard",
    response_model=list[TeamScoreboardItem],
)
async def season_scoreboard(
    season_id: int, db: DbSession, user: CurrentUser
) -> list[TeamScoreboardItem]:
    """시즌 전체 팀 누적 점수 랭킹 (점수 0 팀 포함, 내림차순)."""
    return await score_service.season_scoreboard(db, season_id)


@router.patch("/scores/{score_id}", response_model=ScoreRead)
async def update_score(
    score_id: int, payload: ScoreUpdate, db: DbSession, admin: AdminUser
) -> ScoreRead:
    score = await score_service.get_score(db, score_id)
    if score is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="점수 기록을 찾을 수 없습니다."
        )
    return await score_service.update_score(db, score, payload, admin.id)
