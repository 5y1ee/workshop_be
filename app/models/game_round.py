"""게임 세션 내부 진행도(라운드) 모델.

game_sessions.state 가 매크로 단계(idle..done)라면, game_rounds 는 그 안의
마이크로 진행도다. 예) 노래맞추기 10문제 = 라운드 10개.
vote_ballots / vote_records 패턴을 그대로 따른다.
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin


class GameRound(Base, TimestampMixin):
    __tablename__ = "game_rounds"
    __table_args__ = (
        CheckConstraint(
            "status IN ('waiting', 'open', 'closed')",
            name="game_rounds_status_check",
        ),
        CheckConstraint(
            "tap_mode IS NULL OR tap_mode IN ('count', 'speed', 'timing')",
            name="game_rounds_tap_mode_check",
        ),
        UniqueConstraint(
            "session_id", "order_index", name="uq_game_rounds_session_order"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", name="fk_game_rounds_session"),
        nullable=False,
        comment="연결된 게임 세션 ID",
    )
    order_index: Mapped[int] = mapped_column(
        nullable=False, comment="세션 내 라운드 순서 (1..N)"
    )
    status: Mapped[str] = mapped_column(
        String(10),
        server_default=text("'waiting'"),
        nullable=False,
        comment="라운드 상태 (waiting/open/closed)",
    )
    prompt: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="문제/힌트 텍스트"
    )
    media_url: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="문제용 미디어 URL (노래 파일 등)"
    )
    options: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, comment="button 타입 보기 목록 (예: ['1번','2번','3번','4번'])"
    )
    correct_answer: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="정답 (공개 전 비노출 — 룰렛 seed 처럼 응답에서 숨김)",
    )
    hint_revealed: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
        comment="chat 타입 힌트 공개 여부",
    )
    opened_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="라운드 오픈 시각"
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="라운드 마감 시각"
    )
    # tap 게임 전용 필드
    tap_mode: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="tap 게임 모드 (count/speed/timing)"
    )
    duration: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="tap count 모드 타이머(초)"
    )
    target_time: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="tap timing 모드 목표 시간(초, 0.1 단위)"
    )
    signal_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="tap speed 모드 신호 발사 시각"
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_game_rounds_created_by"),
        nullable=True,
        comment="라운드 생성한 운영자",
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_game_rounds_updated_by"),
        nullable=True,
        comment="라운드 상태 변경한 운영자",
    )

    # --- relationships ---
    session: Mapped["GameSession"] = relationship(back_populates="rounds")
    submissions: Mapped[list["RoundSubmission"]] = relationship(
        back_populates="round"
    )
    tap_logs: Mapped[list["TapLog"]] = relationship(back_populates="round")


class RoundSubmission(Base, CreatedAtMixin):
    """button/vote 타입의 라운드별 1인 1답 제출 (vote_records 패턴).

    chat 타입은 다회 입력이라 기존 GameChatLog 를 사용한다.
    """

    __tablename__ = "round_submissions"
    __table_args__ = (
        UniqueConstraint(
            "round_id", "user_id", name="uq_round_submissions_round_user"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[int] = mapped_column(
        ForeignKey("game_rounds.id", name="fk_round_submissions_round"),
        nullable=False,
        comment="연결된 라운드 ID",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_round_submissions_user"),
        nullable=False,
        comment="제출 유저 ID",
    )
    answer: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="선택/제출한 답"
    )
    is_correct: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False, comment="정답 여부"
    )
    server_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="서버 수신 타임스탬프 (클라이언트 시간 무시)"
    )

    # --- relationships ---
    round: Mapped["GameRound"] = relationship(back_populates="submissions")


class TapLog(Base, CreatedAtMixin):
    """tap 게임 count 모드의 개별 탭 기록. 한 라운드에 한 유저가 여러 번 탭 가능."""

    __tablename__ = "tap_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[int] = mapped_column(
        ForeignKey("game_rounds.id", name="fk_tap_logs_round"),
        nullable=False,
        comment="연결된 라운드 ID",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_tap_logs_user"),
        nullable=False,
        comment="탭한 유저 ID",
    )
    server_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="서버 수신 타임스탬프"
    )

    # --- relationships ---
    round: Mapped["GameRound"] = relationship(back_populates="tap_logs")
