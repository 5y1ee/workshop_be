"""서버 → 클라이언트 이벤트 브로드캐스트.

REST API 등에서 발생한 상태 변화를 WebSocket 접속자에게 알린다.
manager 싱글턴을 통해 같은 프로세스의 모든 연결로 전송된다.
"""

from typing import TYPE_CHECKING

from app.models.game_round import GameRound
from app.models.game_session import GameChatLog, GameResult, GameScoreLog, GameSession
from app.websocket.manager import manager

if TYPE_CHECKING:
    from app.schemas.game_round import TapResult


async def broadcast_session_state(session: GameSession) -> None:
    """게임 세션 상태 변경을 전체 접속자에게 브로드캐스트."""
    await manager.broadcast(
        {
            "type": "session_state_changed",
            "session_id": session.id,
            "timetable_id": session.timetable_id,
            "state": session.state,
        }
    )


async def broadcast_score_recorded(score: GameScoreLog) -> None:
    """점수 기록을 전체 접속자에게 브로드캐스트 (라이브 스코어보드)."""
    await manager.broadcast(
        {
            "type": "score_recorded",
            "session_id": score.session_id,
            "subject_type": score.subject_type,
            "subject_id": score.subject_id,
            "chat_log_id": score.chat_log_id,
            "score": score.score,
        }
    )


async def broadcast_result_recorded(result: GameResult) -> None:
    """최종 결과 기록을 전체 접속자에게 브로드캐스트."""
    await manager.broadcast(
        {
            "type": "result_recorded",
            "session_id": result.session_id,
            "subject_type": result.subject_type,
            "subject_id": result.subject_id,
        }
    )


async def broadcast_round_started(round_: GameRound) -> None:
    """라운드 오픈을 같은 세션 접속자에게 알린다. 정답(correct_answer)은 비노출.

    tap 게임은 클라이언트가 fetch 없이도 즉시 패널을 띄울 수 있도록 추가 필드 포함.
    opened_at(ISO) 을 기준으로 클라이언트가 서버 시간에 맞춰 타이머를 계산한다.
    """
    await manager.broadcast_to_session(
        round_.session_id,
        {
            "type": "round_started",
            "session_id": round_.session_id,
            "round_id": round_.id,
            "order_index": round_.order_index,
            "prompt": round_.prompt,
            "media_url": round_.media_url,
            "options": round_.options,
            # 추가 — tap 게임 시작 동기화에 필요
            "tap_mode": round_.tap_mode,
            "duration": round_.duration,
            "target_time": round_.target_time,
            "opened_at": round_.opened_at.isoformat() if round_.opened_at else None,
            "status": round_.status,
        },
    )


async def broadcast_round_revealed(
    round_: GameRound, total_submissions: int, distribution: dict[str, int]
) -> None:
    """라운드 마감 + 정답/분포 공개를 같은 세션 접속자에게 알린다."""
    await manager.broadcast_to_session(
        round_.session_id,
        {
            "type": "round_revealed",
            "session_id": round_.session_id,
            "round_id": round_.id,
            "order_index": round_.order_index,
            "correct_answer": round_.correct_answer,
            "total_submissions": total_submissions,
            "distribution": distribution,
        },
    )


async def broadcast_chat_message(chat: GameChatLog, nickname: str) -> None:
    """채팅 1건을 같은 세션 접속자에게 실시간 전파."""
    await manager.broadcast_to_session(
        chat.session_id,
        {
            "type": "chat_message",
            "id": chat.id,
            "session_id": chat.session_id,
            "round_id": chat.round_id,
            "user_id": chat.user_id,
            "nickname": nickname,
            "message": chat.message,
            "is_correct": chat.is_correct,
            "server_time": chat.server_time.isoformat(),
        },
    )


async def broadcast_submission_progress(
    session_id: int, round_id: int, submitted: int
) -> None:
    """button 타입 제출 진행 카운트 전파 (선택값은 비노출, 인원 수만)."""
    await manager.broadcast_to_session(
        session_id,
        {
            "type": "submission_progress",
            "session_id": session_id,
            "round_id": round_id,
            "submitted": submitted,
        },
    )


async def broadcast_tap_signal(round_: GameRound) -> None:
    """speed 모드: 신호 발사를 세션 참가자에게 알린다."""
    await manager.broadcast_to_session(
        round_.session_id,
        {
            "type": "tap_signal",
            "session_id": round_.session_id,
            "round_id": round_.id,
            "signal_time": round_.signal_at.isoformat() if round_.signal_at else None,
        },
    )


async def broadcast_tap_closed(
    round_: GameRound, results: list["TapResult"]
) -> None:
    """tap 게임 마감 결과를 세션 참가자에게 전송."""
    await manager.broadcast_to_session(
        round_.session_id,
        {
            "type": "tap_closed",
            "session_id": round_.session_id,
            "round_id": round_.id,
            "tap_mode": round_.tap_mode,
            "target_time": round_.target_time,
            "results": [
                {
                    "user_id": r.user_id,
                    "nickname": r.nickname,
                    "team_name": r.team_name,
                    "value": r.value,
                    "rank": r.rank,
                }
                for r in results
            ],
        },
    )


async def broadcast_tap_progress(
    session_id: int, round_id: int, counts: list[dict]
) -> None:
    """count 모드: 운영자에게만 참가자별 누적 탭 수를 0.5초 간격으로 송신.

    counts: [{"user_id": int, "nickname": str, "team_name": str | None, "count": int}, ...]
    공정성을 위해 참가자에게는 전달하지 않는다.
    """
    await manager.broadcast_to_session_admins(
        session_id,
        {
            "type": "tap_progress",
            "session_id": session_id,
            "round_id": round_id,
            "counts": counts,
        },
    )


async def broadcast_tap_submitted(
    session_id: int,
    round_id: int,
    user_id: int,
    nickname: str,
    team_name: str | None,
    value: float,
    tap_mode: str,
) -> None:
    """speed/timing 모드: 운영자에게만 제출 사실 + 기록 즉시 송신.

    value 의미: speed=반응시간(ms), timing=경과 초(0.1 단위).
    공정성을 위해 참가자에게는 전달하지 않는다.
    """
    await manager.broadcast_to_session_admins(
        session_id,
        {
            "type": "tap_submitted",
            "session_id": session_id,
            "round_id": round_id,
            "user_id": user_id,
            "nickname": nickname,
            "team_name": team_name,
            "value": value,
            "tap_mode": tap_mode,
        },
    )


async def broadcast_roulette_result(
    session_id: int, nonce: int, selected_index: int, selected: str
) -> None:
    """룰렛/추첨 결과를 전체 접속자에게 브로드캐스트."""
    await manager.broadcast(
        {
            "type": "roulette_result",
            "session_id": session_id,
            "nonce": nonce,
            "selected_index": selected_index,
            "selected": selected,
        }
    )
