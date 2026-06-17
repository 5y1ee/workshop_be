"""서버 → 클라이언트 이벤트 브로드캐스트.

REST API 등에서 발생한 상태 변화를 WebSocket 접속자에게 알린다.
manager 싱글턴을 통해 같은 프로세스의 모든 연결로 전송된다.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.models.game_round import GameRound
from app.models.game_session import GameChatLog, GameResult, GameScoreLog, GameSession
from app.models.notice import Notice
from app.models.speaking import SpeakingEvent, SpeakingGrant
from app.websocket.manager import manager

if TYPE_CHECKING:
    from app.schemas.game_round import TapResult
    from app.schemas.speaking import SpeakingResult


def _iso_utc(dt: datetime | None) -> str | None:
    """서버 시각을 UTC 명시(`Z`) ISO 문자열로 직렬화.

    DB의 datetime 은 timezone-naive(UTC) 로 저장되므로 그대로 isoformat() 하면
    JS new Date() 가 로컬 시간으로 해석하는 문제가 있어 'Z' 접미사로 UTC 명시.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat() + "Z"


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


async def broadcast_timetable_changed(
    season_id: int, entry_id: int | None, action: str
) -> None:
    """타임테이블 생성/수정/삭제를 전체 접속자에게 브로드캐스트."""
    await manager.broadcast(
        {
            "type": "timetable_changed",
            "season_id": season_id,
            "entry_id": entry_id,
            "action": action,
        }
    )


async def broadcast_hidden_role_changed(
    season_id: int | None, user_id: int | None, action: str
) -> None:
    await manager.broadcast(
        {
            "type": "hidden_role_changed",
            "season_id": season_id,
            "user_id": user_id,
            "action": action,
        }
    )


async def broadcast_team_buff_changed(
    session_id: int | None, team_id: int | None, action: str
) -> None:
    await manager.broadcast(
        {
            "type": "team_buff_changed",
            "session_id": session_id,
            "team_id": team_id,
            "action": action,
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


async def broadcast_round_started(round_: GameRound, reveal_prompt: bool = True) -> None:
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
            "prompt": round_.prompt if reveal_prompt else None,
            "media_url": round_.media_url,
            "options": round_.options,
            "hint_revealed": round_.hint_revealed,
            # 추가 — tap 게임 시작 동기화에 필요
            "tap_mode": round_.tap_mode,
            "duration": round_.duration,
            "target_time": round_.target_time,
            "opened_at": _iso_utc(round_.opened_at),
            "status": round_.status,
        },
    )


async def broadcast_round_hint_revealed(round_: GameRound) -> None:
    """chat 라운드 힌트 공개를 같은 세션 접속자에게 알린다."""
    await manager.broadcast_to_session(
        round_.session_id,
        {
            "type": "round_hint_revealed",
            "session_id": round_.session_id,
            "round_id": round_.id,
            "order_index": round_.order_index,
            "prompt": round_.prompt,
            "hint_revealed": round_.hint_revealed,
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


async def broadcast_notice_created(notice: Notice) -> None:
    """시즌 공지 생성/교체를 전체 접속자에게 전파."""
    await manager.broadcast(
        {
            "type": "notice_created",
            "notice": {
                "id": notice.id,
                "season_id": notice.season_id,
                "message": notice.message,
                "expires_at": _iso_utc(notice.expires_at),
                "created_by": notice.created_by,
                "deleted_at": _iso_utc(notice.deleted_at),
                "created_at": _iso_utc(notice.created_at),
            },
        }
    )


async def broadcast_notice_deleted(season_id: int, notice_id: int) -> None:
    """시즌 공지 삭제를 전체 접속자에게 전파."""
    await manager.broadcast(
        {
            "type": "notice_deleted",
            "season_id": season_id,
            "notice_id": notice_id,
        }
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
            "server_time": _iso_utc(chat.server_time),
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
            "signal_time": _iso_utc(round_.signal_at),
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
                    "team_id": r.team_id,
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


async def broadcast_speaking_event_started(event: SpeakingEvent) -> None:
    """전역 발언권 이벤트 시작을 전체 접속자에게 알린다."""
    await manager.broadcast(
        {
            "type": "speaking_event_started",
            "season_id": event.season_id,
            "event_id": event.id,
            "mode": event.mode,
            "status": event.status,
            "duration": event.duration,
            "target_time": event.target_time,
            "opened_at": _iso_utc(event.opened_at),
        }
    )


async def broadcast_speaking_signal(event: SpeakingEvent) -> None:
    """발언권 speed 모드 신호를 전체 접속자에게 알린다."""
    await manager.broadcast(
        {
            "type": "speaking_signal",
            "season_id": event.season_id,
            "event_id": event.id,
            "signal_time": _iso_utc(event.signal_at),
        }
    )


async def broadcast_speaking_event_closed(
    event: SpeakingEvent, results: list["SpeakingResult"]
) -> None:
    """발언권 이벤트 마감 결과를 전체 접속자에게 전송한다."""
    await manager.broadcast(
        {
            "type": "speaking_event_closed",
            "season_id": event.season_id,
            "event_id": event.id,
            "mode": event.mode,
            "status": event.status,
            "target_time": event.target_time,
            "closed_at": _iso_utc(event.closed_at),
            "results": [
                {
                    "user_id": r.user_id,
                    "nickname": r.nickname,
                    "team_id": r.team_id,
                    "team_name": r.team_name,
                    "value": r.value,
                    "rank": r.rank,
                    "granted": r.granted,
                }
                for r in results
            ],
        }
    )


async def broadcast_speaking_progress(
    season_id: int, event_id: int, counts: list[dict]
) -> None:
    """발언권 count 모드 진행 현황을 운영자에게만 송신."""
    await manager.broadcast_to_admins(
        {
            "type": "speaking_progress",
            "season_id": season_id,
            "event_id": event_id,
            "counts": counts,
        }
    )


async def broadcast_speaking_submitted(
    season_id: int,
    event_id: int,
    user_id: int,
    nickname: str,
    team_name: str | None,
    value: float,
    mode: str,
) -> None:
    """발언권 speed/timing 제출 도착을 운영자에게만 송신."""
    await manager.broadcast_to_admins(
        {
            "type": "speaking_submitted",
            "season_id": season_id,
            "event_id": event_id,
            "user_id": user_id,
            "nickname": nickname,
            "team_name": team_name,
            "value": value,
            "mode": mode,
        }
    )


async def broadcast_speaking_granted(
    event: SpeakingEvent, grant: SpeakingGrant, result: "SpeakingResult"
) -> None:
    """운영자가 특정 참가자에게 발언권을 부여했음을 전파."""
    await manager.broadcast(
        {
            "type": "speaking_granted",
            "season_id": event.season_id,
            "event_id": event.id,
            "grant_id": grant.id,
            "user_id": grant.user_id,
            "nickname": result.nickname,
            "rank": grant.rank,
            "value": grant.value,
            "granted_at": _iso_utc(grant.granted_at),
        }
    )


async def broadcast_speaking_event_dismissed(event: SpeakingEvent) -> None:
    """운영자가 종료된 발언권 창을 모든 접속자 화면에서 닫도록 알린다."""
    await manager.broadcast(
        {
            "type": "speaking_event_dismissed",
            "season_id": event.season_id,
            "event_id": event.id,
        }
    )


async def broadcast_reward_claimed(
    reward_id: int,
    reward_name: str,
    user_id: int,
    nickname: str,
    claimed_count: int,
    total_count: int,
) -> None:
    """리워드 수령을 전체 접속자에게 브로드캐스트 (도감 실시간 업데이트)."""
    await manager.broadcast(
        {
            "type": "reward_claimed",
            "reward_id": reward_id,
            "reward_name": reward_name,
            "user_id": user_id,
            "nickname": nickname,
            "claimed_count": claimed_count,
            "remaining_count": total_count - claimed_count,
        }
    )


async def broadcast_reward_unclaimed(
    reward_id: int,
    claimed_count: int,
    total_count: int,
) -> None:
    """리워드 수령 취소를 전체 접속자에게 브로드캐스트."""
    await manager.broadcast(
        {
            "type": "reward_unclaimed",
            "reward_id": reward_id,
            "claimed_count": claimed_count,
            "remaining_count": total_count - claimed_count,
        }
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
