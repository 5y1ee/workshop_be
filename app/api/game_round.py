import asyncio

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.models.game_round import GameRound
from app.schemas.game_round import (
    ChatLogRead,
    QuizSubmissionRead,
    RoundCreate,
    RoundRead,
    RoundReveal,
    RoundUpdate,
)
from app.services import game_round_service, game_session_service
from app.services.game_round_service import RoundConflict, RoundDeleteBlocked
from app.websocket.events import (
    broadcast_round_hint_revealed,
    broadcast_session_state,
    broadcast_round_revealed,
    broadcast_round_started,
    broadcast_tap_closed,
)

router = APIRouter(tags=["game-rounds"])


async def _get_session_or_404(db: DbSession, session_id: int):
    session = await game_session_service.get_session(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="게임 세션을 찾을 수 없습니다."
        )
    return session


async def _get_round_or_404(db: DbSession, round_id: int) -> GameRound:
    round_ = await game_round_service.get_round(db, round_id)
    if round_ is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="라운드를 찾을 수 없습니다."
        )
    return round_


async def _reveal_for(db: DbSession, round_: GameRound) -> RoundReveal:
    total, dist = await game_round_service.round_distribution(db, round_.id)
    return RoundReveal(
        round_id=round_.id,
        correct_answer=round_.correct_answer,
        total_submissions=total,
        distribution=dist,
    )


def _round_read(round_: GameRound, input_type: str | None, is_admin: bool) -> RoundRead:
    data = RoundRead.model_validate(round_)
    if input_type == "chat" and not is_admin and not round_.hint_revealed:
        return data.model_copy(update={"prompt": None})
    return data


@router.post(
    "/sessions/{session_id}/rounds",
    response_model=RoundRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_round(
    session_id: int, payload: RoundCreate, db: DbSession, admin: AdminUser
) -> RoundRead:
    await _get_session_or_404(db, session_id)
    round_ = await game_round_service.create_round(db, session_id, payload, admin.id)
    input_type = await game_round_service.round_input_type(db, round_)
    return _round_read(round_, input_type, is_admin=True)


@router.get("/sessions/{session_id}/rounds", response_model=list[RoundRead])
async def list_rounds(
    session_id: int, db: DbSession, user: CurrentUser
) -> list[RoundRead]:
    rounds = await game_round_service.list_rounds(db, session_id)
    input_types = await game_round_service.round_input_types(db, rounds)
    return [
        _round_read(round_, input_types.get(round_.id), is_admin=user.role == "admin")
        for round_ in rounds
    ]


@router.get("/sessions/{session_id}/rounds/current", response_model=RoundRead)
async def current_round(
    session_id: int, db: DbSession, user: CurrentUser
) -> RoundRead:
    """재접속 시 현재 진행 중인 라운드 복구용."""
    round_ = await game_round_service.get_open_round(db, session_id)
    if round_ is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="진행 중인 라운드가 없습니다.",
        )
    input_type = await game_round_service.round_input_type(db, round_)
    return _round_read(round_, input_type, is_admin=user.role == "admin")


@router.get("/sessions/{session_id}/chat-logs", response_model=list[ChatLogRead])
async def list_chat_logs(
    session_id: int,
    db: DbSession,
    admin: AdminUser,
    round_id: int | None = Query(default=None),
) -> list[dict]:
    await _get_session_or_404(db, session_id)
    return await game_round_service.list_chat_logs(db, session_id, round_id)


@router.get("/rounds/{round_id}", response_model=RoundRead)
async def get_round(round_id: int, db: DbSession, user: CurrentUser) -> RoundRead:
    round_ = await _get_round_or_404(db, round_id)
    input_type = await game_round_service.round_input_type(db, round_)
    return _round_read(round_, input_type, is_admin=user.role == "admin")


@router.patch("/rounds/{round_id}", response_model=RoundRead)
async def update_round(
    round_id: int, payload: RoundUpdate, db: DbSession, admin: AdminUser
) -> RoundRead:
    round_ = await _get_round_or_404(db, round_id)
    round_ = await game_round_service.update_round(db, round_, payload, admin.id)
    input_type = await game_round_service.round_input_type(db, round_)
    return _round_read(round_, input_type, is_admin=True)


@router.delete("/rounds/{round_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_round(round_id: int, db: DbSession, admin: AdminUser) -> None:
    round_ = await _get_round_or_404(db, round_id)
    try:
        await game_round_service.delete_round(db, round_)
    except RoundDeleteBlocked as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post("/rounds/{round_id}/open", response_model=RoundRead)
async def open_round(
    round_id: int, db: DbSession, admin: AdminUser
) -> RoundRead:
    round_ = await _get_round_or_404(db, round_id)
    session = await _get_session_or_404(db, round_.session_id)
    if session.state == "idle":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="세션을 준비 상태로 변경한 뒤 라운드를 오픈하세요.",
        )
    if session.state == "ready":
        session = await game_session_service.transition(
            db, session, "in_progress", admin.id
        )
        await broadcast_session_state(session)
    elif session.state != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="진행중 상태에서만 라운드를 오픈할 수 있습니다.",
        )
    try:
        round_ = await game_round_service.open_round(db, round_, admin.id)
    except RoundConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    input_type = await game_round_service.round_input_type(db, round_)
    await broadcast_round_started(
        round_, reveal_prompt=input_type != "chat" or round_.hint_revealed
    )
    # tap count 모드: duration 초 후 자동 마감 + 0.5초 간격 진행 broadcast
    if round_.tap_mode == "count" and round_.duration:
        asyncio.create_task(
            game_round_service._auto_close_tap_round(round_.id, round_.duration)
        )
        asyncio.create_task(
            game_round_service._tap_progress_loop(
                round_.id, round_.session_id, round_.duration
            )
        )
    return _round_read(round_, input_type, is_admin=True)


@router.post("/rounds/{round_id}/hint/reveal", response_model=RoundRead)
async def reveal_round_hint(
    round_id: int, db: DbSession, admin: AdminUser
) -> RoundRead:
    round_ = await _get_round_or_404(db, round_id)
    round_ = await game_round_service.reveal_hint(db, round_, admin.id)
    input_type = await game_round_service.round_input_type(db, round_)
    await broadcast_round_hint_revealed(round_)
    return _round_read(round_, input_type, is_admin=True)


@router.post("/rounds/{round_id}/close", response_model=RoundReveal)
async def close_round(
    round_id: int, db: DbSession, admin: AdminUser
) -> RoundReveal:
    round_ = await _get_round_or_404(db, round_id)
    try:
        round_ = await game_round_service.close_round(db, round_, admin.id)
    except RoundConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    # tap 게임이면 결과도 함께 브로드캐스트
    if round_.tap_mode:
        results = await game_round_service.get_tap_results(db, round_)
        await broadcast_tap_closed(round_, results)
    reveal = await _reveal_for(db, round_)
    await broadcast_round_revealed(round_, reveal.total_submissions, reveal.distribution)
    return reveal


@router.post("/rounds/{round_id}/signal", status_code=status.HTTP_202_ACCEPTED)
async def send_tap_signal(round_id: int, db: DbSession, admin: AdminUser) -> dict:
    """speed 모드: 랜덤 딜레이(3~5초) 후 tap_signal 이벤트 발사."""
    round_ = await _get_round_or_404(db, round_id)
    if round_.tap_mode != "speed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="speed 모드 라운드에만 사용할 수 있습니다.",
        )
    if round_.status != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="열려 있는(open) 라운드에만 신호를 보낼 수 있습니다.",
        )
    asyncio.create_task(game_round_service._send_tap_signal(round_.id))
    return {"status": "signaling"}


@router.get(
    "/rounds/{round_id}/submissions", response_model=list[QuizSubmissionRead]
)
async def list_round_submissions(
    round_id: int, db: DbSession, admin: AdminUser
) -> list[dict]:
    """button/vote 라운드 제출 목록 (운영자 채점용)."""
    round_ = await _get_round_or_404(db, round_id)
    return await game_round_service.list_submissions(db, round_)


@router.get("/rounds/{round_id}/reveal", response_model=RoundReveal)
async def reveal_round(
    round_id: int, db: DbSession, admin: AdminUser
) -> RoundReveal:
    round_ = await _get_round_or_404(db, round_id)
    return await _reveal_for(db, round_)
