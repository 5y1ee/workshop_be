from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.game_session import GameSessionRead, SessionTransition
from app.services import game_session_service, timetable_service
from app.services.game_session_service import InvalidStateTransition

router = APIRouter(tags=["game-sessions"])


async def _get_session_or_404(db: DbSession, session_id: int):
    session = await game_session_service.get_session(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="게임 세션을 찾을 수 없습니다."
        )
    return session


@router.post(
    "/timetable/{timetable_id}/session",
    response_model=GameSessionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    timetable_id: int, db: DbSession, admin: AdminUser
) -> GameSessionRead:
    if await timetable_service.get_entry(db, timetable_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="타임테이블 항목을 찾을 수 없습니다.",
        )
    return await game_session_service.create_session(db, timetable_id)


@router.get(
    "/timetable/{timetable_id}/sessions", response_model=list[GameSessionRead]
)
async def list_sessions(
    timetable_id: int, db: DbSession, user: CurrentUser
) -> list[GameSessionRead]:
    return await game_session_service.list_sessions_for_timetable(db, timetable_id)


@router.get("/sessions/{session_id}", response_model=GameSessionRead)
async def get_session(
    session_id: int, db: DbSession, user: CurrentUser
) -> GameSessionRead:
    return await _get_session_or_404(db, session_id)


@router.post("/sessions/{session_id}/transition", response_model=GameSessionRead)
async def transition_session(
    session_id: int, payload: SessionTransition, db: DbSession, admin: AdminUser
) -> GameSessionRead:
    session = await _get_session_or_404(db, session_id)
    try:
        return await game_session_service.transition(db, session, payload.to, admin.id)
    except InvalidStateTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
