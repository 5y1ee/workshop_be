"""WebSocket 클라이언트 → 서버 메시지 핸들러.

메시지 타입별 핸들러를 레지스트리에 등록하고 dispatch() 가 라우팅한다.
새 핸들러는 @register("타입") 데코레이터로 추가하면 된다.

핸들러 시그니처:
    async def handler(ctx: MessageContext, data: dict[str, Any]) -> None
"""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from fastapi import WebSocket
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.services import game_round_service, speaking_service
from app.services.game_round_service import RoundConflict, get_tap_results
from app.services.speaking_service import SpeakingConflict
from app.websocket.events import (
    broadcast_chat_message,
    broadcast_speaking_submitted,
    broadcast_submission_progress,
    broadcast_tap_closed,
    broadcast_tap_submitted,
)
from app.websocket.manager import manager as _manager

if TYPE_CHECKING:
    from app.websocket.manager import ConnectionManager


class MessageContext:
    """핸들러가 응답을 보낼 때 필요한 컨텍스트."""

    def __init__(
        self,
        websocket: WebSocket,
        manager: "ConnectionManager",
        user_id: int,
        team_id: int | None,
    ) -> None:
        self.websocket = websocket
        self.manager = manager
        self.user_id = user_id
        self.team_id = team_id


Handler = Callable[[MessageContext, dict[str, Any]], Awaitable[None]]

_HANDLERS: dict[str, Handler] = {}


def register(msg_type: str) -> Callable[[Handler], Handler]:
    def decorator(fn: Handler) -> Handler:
        _HANDLERS[msg_type] = fn
        return fn

    return decorator


async def dispatch(ctx: MessageContext, data: dict[str, Any]) -> None:
    """수신 메시지를 타입에 맞는 핸들러로 전달."""
    msg_type = data.get("type")
    handler = _HANDLERS.get(msg_type)
    if handler is None:
        await ctx.websocket.send_json(
            {"type": "error", "detail": f"알 수 없는 메시지 타입: {msg_type!r}"}
        )
        return
    await handler(ctx, data)


async def _error(ctx: MessageContext, detail: str) -> None:
    await ctx.websocket.send_json({"type": "error", "detail": detail})


@register("ping")
async def _handle_ping(ctx: MessageContext, data: dict[str, Any]) -> None:
    await ctx.websocket.send_json({"type": "pong"})


@register("join_session")
async def _handle_join_session(ctx: MessageContext, data: dict[str, Any]) -> None:
    """게임 상세 페이지 진입 — 해당 세션의 실시간 방에 합류."""
    session_id = data.get("session_id")
    if not isinstance(session_id, int):
        await _error(ctx, "session_id(정수)가 필요합니다.")
        return
    ctx.manager.join_session(session_id, ctx.user_id)
    await ctx.websocket.send_json({"type": "session_joined", "session_id": session_id})


@register("leave_session")
async def _handle_leave_session(ctx: MessageContext, data: dict[str, Any]) -> None:
    session_id = data.get("session_id")
    if isinstance(session_id, int):
        ctx.manager.leave_session(session_id, ctx.user_id)


@register("chat_message")
async def _handle_chat_message(ctx: MessageContext, data: dict[str, Any]) -> None:
    """chat 타입 게임의 채팅 입력. 현재 열린 라운드 기준으로 정답 판정 후 전파."""
    session_id = data.get("session_id")
    message = data.get("message")
    if not isinstance(session_id, int) or not isinstance(message, str):
        await _error(ctx, "session_id(정수)와 message(문자열)가 필요합니다.")
        return
    message = message.strip()
    if not message:
        return

    async with AsyncSessionLocal() as db:
        round_ = await game_round_service.get_open_round(db, session_id)
        chat = await game_round_service.record_chat(
            db, session_id, round_, ctx.user_id, message
        )
        nickname = await db.scalar(
            select(User.nickname).where(User.id == ctx.user_id)
        )

    await broadcast_chat_message(chat, nickname or "익명")


@register("submit_answer")
async def _handle_submit_answer(ctx: MessageContext, data: dict[str, Any]) -> None:
    """button/vote 타입 게임의 보기 선택 제출. 1인 1답."""
    round_id = data.get("round_id")
    answer = data.get("answer")
    if not isinstance(round_id, int) or not isinstance(answer, str):
        await _error(ctx, "round_id(정수)와 answer(문자열)가 필요합니다.")
        return

    async with AsyncSessionLocal() as db:
        round_ = await game_round_service.get_round(db, round_id)
        if round_ is None:
            await _error(ctx, "라운드를 찾을 수 없습니다.")
            return
        try:
            await game_round_service.submit_answer(
                db, round_, ctx.user_id, answer
            )
        except RoundConflict as exc:
            await _error(ctx, str(exc))
            return
        total, _dist = await game_round_service.round_distribution(db, round_id)

    # 제출자 본인에게는 접수 확인만 (정답 여부는 공정성상 마감 때 공개)
    await ctx.websocket.send_json(
        {"type": "submission_accepted", "round_id": round_id}
    )
    # 같은 세션 전체에는 제출 인원 수만 갱신
    await broadcast_submission_progress(round_.session_id, round_id, total)


@register("tap_press")
async def _handle_tap_press(ctx: MessageContext, data: dict[str, Any]) -> None:
    """tap 게임 버튼 입력.
    - count 모드: TapLog 에 기록 (다회 가능)
    - speed 모드: 반응시간(ms) 을 RoundSubmission 에 1회 기록
    - timing 모드: 경과시간(초, 0.1 단위) 을 RoundSubmission 에 1회 기록
    """
    round_id = data.get("round_id")
    elapsed = data.get("elapsed")  # speed: ms(float), timing: 초(float), count: 무시

    if not isinstance(round_id, int):
        await _error(ctx, "round_id(정수)가 필요합니다.")
        return

    async with AsyncSessionLocal() as db:
        round_ = await game_round_service.get_round(db, round_id)
        if round_ is None:
            await _error(ctx, "라운드를 찾을 수 없습니다.")
            return
        if round_.tap_mode is None:
            await _error(ctx, "tap 게임 라운드가 아닙니다.")
            return

        # speed 모드: 신호(signal_at) 전에 누르면 부정출발 → 실격 처리
        if round_.tap_mode == "speed" and round_.signal_at is None:
            await _disqualify_tap(ctx, db, round_)
            return

        try:
            if round_.tap_mode == "count":
                await game_round_service.record_tap_count(db, round_, ctx.user_id)
            else:
                if not isinstance(elapsed, (int, float)):
                    await _error(ctx, "elapsed(숫자)가 필요합니다.")
                    return
                value = str(round(float(elapsed), 1))
                await game_round_service.record_tap_once(db, round_, ctx.user_id, value)
        except RoundConflict:
            # speed/timing 모드 중복 제출은 조용히 무시 (이미 기록됨)
            return

        # speed/timing: 운영자에게만 제출 사실 + 기록 즉시 송신
        if round_.tap_mode in ("speed", "timing"):
            info = await game_round_service._user_info(db, round_)
            who = info.get(ctx.user_id, {"nickname": f"user#{ctx.user_id}", "team_name": None})
            await broadcast_tap_submitted(
                session_id=round_.session_id,
                round_id=round_.id,
                user_id=ctx.user_id,
                nickname=who["nickname"],
                team_name=who["team_name"],
                value=float(elapsed),
                tap_mode=round_.tap_mode,
            )

    await ctx.websocket.send_json({"type": "tap_accepted", "round_id": round_id})


@register("tap_false_start")
async def _handle_tap_false_start(ctx: MessageContext, data: dict[str, Any]) -> None:
    """speed 모드 부정출발: 신호('지금!') 전에 버튼을 누른 사용자를 실격 처리.

    프런트가 신호 전 입력을 명시적으로 보낸다. 서버는 speed 모드 + open 상태에서만
    실격을 기록한다.
    """
    round_id = data.get("round_id")
    if not isinstance(round_id, int):
        await _error(ctx, "round_id(정수)가 필요합니다.")
        return

    async with AsyncSessionLocal() as db:
        round_ = await game_round_service.get_round(db, round_id)
        if round_ is None or round_.tap_mode != "speed":
            return
        await _disqualify_tap(ctx, db, round_)


async def _disqualify_tap(ctx: MessageContext, db: Any, round_: Any) -> None:
    """speed 부정출발 실격을 기록하고 본인 + 운영자에게 알린다 (중복 시 무시)."""
    try:
        await game_round_service.record_tap_disqualify(db, round_, ctx.user_id)
    except RoundConflict:
        # 이미 실격/제출됨 → 조용히 무시
        return
    info = await game_round_service._user_info(db, round_)
    who = info.get(ctx.user_id, {"nickname": f"user#{ctx.user_id}", "team_name": None})
    await broadcast_tap_submitted(
        session_id=round_.session_id,
        round_id=round_.id,
        user_id=ctx.user_id,
        nickname=who["nickname"],
        team_name=who["team_name"],
        value=0.0,
        tap_mode="speed",
        disqualified=True,
    )
    await ctx.websocket.send_json(
        {"type": "tap_disqualified", "round_id": round_.id}
    )


@register("speaking_press")
async def _handle_speaking_press(ctx: MessageContext, data: dict[str, Any]) -> None:
    """전역 발언권 이벤트 버튼 입력."""
    event_id = data.get("event_id")
    value = data.get("value")
    if not isinstance(event_id, int):
        await _error(ctx, "event_id(정수)가 필요합니다.")
        return

    async with AsyncSessionLocal() as db:
        event = await speaking_service.get_event(db, event_id)
        if event is None:
            await _error(ctx, "발언권 이벤트를 찾을 수 없습니다.")
            return

        # speed 모드: 신호(signal_at) 전에 누르면 부정출발 → 실격 처리
        if event.mode == "speed" and event.signal_at is None:
            await _disqualify_speaking(ctx, db, event)
            return

        try:
            if event.mode == "count":
                await speaking_service.record_count(db, event, ctx.user_id)
            else:
                if not isinstance(value, (int, float)):
                    await _error(ctx, "value(숫자)가 필요합니다.")
                    return
                await speaking_service.record_once(db, event, ctx.user_id, float(value))
        except SpeakingConflict as exc:
            await _error(ctx, str(exc))
            return

        if event.mode in ("speed", "timing"):
            who = await speaking_service.user_info_for_event(db, event, ctx.user_id)
            await broadcast_speaking_submitted(
                season_id=event.season_id,
                event_id=event.id,
                user_id=ctx.user_id,
                nickname=who["nickname"],
                team_name=who["team_name"],
                value=float(value),
                mode=event.mode,
            )

    await ctx.websocket.send_json({"type": "speaking_accepted", "event_id": event_id})


@register("speaking_false_start")
async def _handle_speaking_false_start(ctx: MessageContext, data: dict[str, Any]) -> None:
    """발언권 speed 모드 부정출발: 신호 전에 버튼을 누른 사용자를 실격 처리."""
    event_id = data.get("event_id")
    if not isinstance(event_id, int):
        await _error(ctx, "event_id(정수)가 필요합니다.")
        return

    async with AsyncSessionLocal() as db:
        event = await speaking_service.get_event(db, event_id)
        if event is None or event.mode != "speed":
            return
        await _disqualify_speaking(ctx, db, event)


async def _disqualify_speaking(ctx: MessageContext, db: Any, event: Any) -> None:
    """발언권 speed 부정출발 실격을 기록하고 본인 + 운영자에게 알린다 (중복 시 무시)."""
    try:
        await speaking_service.record_disqualify(db, event, ctx.user_id)
    except SpeakingConflict:
        return
    who = await speaking_service.user_info_for_event(db, event, ctx.user_id)
    await broadcast_speaking_submitted(
        season_id=event.season_id,
        event_id=event.id,
        user_id=ctx.user_id,
        nickname=who["nickname"],
        team_name=who["team_name"],
        value=0.0,
        mode="speed",
        disqualified=True,
    )
    await ctx.websocket.send_json(
        {"type": "speaking_disqualified", "event_id": event.id}
    )
