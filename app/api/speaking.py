import asyncio

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.models.speaking import SpeakingEvent
from app.schemas.speaking import (
    SpeakingEventCreate,
    SpeakingEventRead,
    SpeakingEventResults,
    SpeakingGrantCreate,
    SpeakingGrantRead,
    SpeakingResult,
)
from app.services import season_service, speaking_service
from app.services.speaking_service import SpeakingConflict
from app.websocket.events import (
    broadcast_speaking_event_dismissed,
    broadcast_speaking_event_closed,
    broadcast_speaking_event_started,
    broadcast_speaking_granted,
)

router = APIRouter(tags=["speaking"])


async def _get_event_or_404(db: DbSession, event_id: int) -> SpeakingEvent:
    event = await speaking_service.get_event(db, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="발언권 이벤트를 찾을 수 없습니다.",
        )
    return event


async def _require_season(db: DbSession, season_id: int) -> None:
    if await season_service.get_season(db, season_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="시즌을 찾을 수 없습니다.",
        )


@router.post(
    "/seasons/{season_id}/speaking-events",
    response_model=SpeakingEventRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_speaking_event(
    season_id: int,
    payload: SpeakingEventCreate,
    db: DbSession,
    admin: AdminUser,
) -> SpeakingEvent:
    await _require_season(db, season_id)
    try:
        event = await speaking_service.create_event(db, season_id, payload, admin.id)
    except SpeakingConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await broadcast_speaking_event_started(event)
    if event.mode == "count" and event.duration:
        asyncio.create_task(speaking_service.auto_close_count_event(event.id, event.duration))
        asyncio.create_task(speaking_service.speaking_progress_loop(event.id, event.duration))
    return event


@router.get(
    "/seasons/{season_id}/speaking-events/current",
    response_model=SpeakingEventRead,
)
async def current_speaking_event(
    season_id: int, db: DbSession, user: CurrentUser
) -> SpeakingEvent:
    event = await speaking_service.get_current_event(db, season_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="진행 중인 발언권 이벤트가 없습니다.",
        )
    return event


@router.post(
    "/speaking-events/{event_id}/signal",
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_speaking_signal(
    event_id: int, db: DbSession, admin: AdminUser
) -> dict:
    event = await _get_event_or_404(db, event_id)
    if event.mode != "speed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="빠르기 대결에서만 신호를 보낼 수 있습니다.",
        )
    if event.status != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="진행 중인 발언권 이벤트가 아닙니다.",
        )
    asyncio.create_task(speaking_service.send_signal_after_delay(event.id))
    return {"status": "signaling"}


@router.post(
    "/speaking-events/{event_id}/close",
    response_model=SpeakingEventResults,
)
async def close_speaking_event(
    event_id: int, db: DbSession, admin: AdminUser
) -> dict:
    event = await _get_event_or_404(db, event_id)
    try:
        event = await speaking_service.close_event(db, event, admin.id)
    except SpeakingConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    results = await speaking_service.get_results(db, event)
    await broadcast_speaking_event_closed(event, results)
    return {"event": event, "results": results}


@router.get(
    "/speaking-events/{event_id}/results",
    response_model=list[SpeakingResult],
)
async def speaking_results(
    event_id: int, db: DbSession, admin: AdminUser
) -> list[SpeakingResult]:
    event = await _get_event_or_404(db, event_id)
    return await speaking_service.get_results(db, event)


@router.post(
    "/speaking-events/{event_id}/grants",
    response_model=SpeakingGrantRead,
    status_code=status.HTTP_201_CREATED,
)
async def grant_speaking_right(
    event_id: int,
    payload: SpeakingGrantCreate,
    db: DbSession,
    admin: AdminUser,
) -> SpeakingGrantRead:
    event = await _get_event_or_404(db, event_id)
    try:
        grant, result = await speaking_service.grant_speaking_right(
            db, event, payload.user_id, admin.id
        )
    except SpeakingConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await broadcast_speaking_granted(event, grant, result)
    return grant


@router.post(
    "/speaking-events/{event_id}/dismiss",
    status_code=status.HTTP_202_ACCEPTED,
)
async def dismiss_speaking_event(
    event_id: int, db: DbSession, admin: AdminUser
) -> dict:
    event = await _get_event_or_404(db, event_id)
    await broadcast_speaking_event_dismissed(event)
    return {"status": "dismissed"}
