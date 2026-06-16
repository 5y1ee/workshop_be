from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin


class GameSession(Base, TimestampMixin):
    __tablename__ = "game_sessions"
    __table_args__ = (
        CheckConstraint(
            "state IN ('idle', 'ready', 'in_progress', 'scoring', 'reward', 'done')",
            name="game_sessions_state_check",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    timetable_id: Mapped[int] = mapped_column(
        ForeignKey("timetable.id", name="fk_game_sessions_timetable"),
        nullable=False,
        comment="연결된 타임테이블 항목 ID",
    )
    state: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'idle'"),
        nullable=False,
        comment="게임 진행 상태 (idle/ready/in_progress/scoring/reward/done)",
    )
    seed: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="룰렛/랜덤 결과 생성용 서버 시드값"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="게임 시작 시각"
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="게임 종료 시각"
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_game_sessions_updated"),
        nullable=True,
        comment="상태 변경한 운영자",
    )

    # --- relationships ---
    timetable: Mapped["Timetable"] = relationship(back_populates="sessions")
    score_logs: Mapped[list["GameScoreLog"]] = relationship(back_populates="session")
    results: Mapped[list["GameResult"]] = relationship(back_populates="session")
    chat_logs: Mapped[list["GameChatLog"]] = relationship(back_populates="session")
    rounds: Mapped[list["GameRound"]] = relationship(back_populates="session")
    envelopes: Mapped[list["Envelope"]] = relationship(
        back_populates="session", foreign_keys="Envelope.session_id"
    )
    raffle_tickets: Mapped[list["RaffleTicket"]] = relationship(
        back_populates="session"
    )


class GameScoreLog(Base, TimestampMixin):
    __tablename__ = "game_score_logs"
    __table_args__ = (
        CheckConstraint(
            "subject_type IN ('team', 'user')",
            name="game_score_logs_subject_type_check",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", name="fk_game_score_logs_session"),
        nullable=False,
        comment="연결된 게임 세션 ID",
    )
    subject_type: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="점수 단위 (team/user)"
    )
    subject_id: Mapped[int] = mapped_column(
        nullable=False, comment="subject_type에 따라 teams.id 또는 users.id"
    )
    chat_log_id: Mapped[int | None] = mapped_column(
        ForeignKey("game_chat_logs.id", name="fk_game_score_logs_chat_log"),
        unique=True,
        nullable=True,
        comment="노래맞추기 정답 후보 채팅 로그 ID",
    )
    score: Mapped[int] = mapped_column(
        server_default=text("0"), nullable=False, comment="획득 점수"
    )
    memo: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="부가정보 (예: 수영 01:23, 자전거 02:45)"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_game_score_logs_created_by"),
        nullable=False,
        comment="점수 기입한 운영자",
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_game_score_logs_updated_by"),
        nullable=True,
        comment="점수 수정한 운영자",
    )

    # --- relationships ---
    session: Mapped["GameSession"] = relationship(back_populates="score_logs")


class GameResult(Base, CreatedAtMixin):
    __tablename__ = "game_results"
    __table_args__ = (
        CheckConstraint(
            "subject_type IN ('team', 'user')",
            name="game_results_subject_type_check",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", name="fk_game_results_session"),
        nullable=False,
        comment="연결된 게임 세션 ID",
    )
    subject_type: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="결과 단위 (team/user)"
    )
    subject_id: Mapped[int] = mapped_column(
        nullable=False, comment="최종 승자 팀/유저 ID"
    )

    # --- relationships ---
    session: Mapped["GameSession"] = relationship(back_populates="results")


class GameChatLog(Base):
    __tablename__ = "game_chat_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", name="fk_game_chat_logs_session"),
        nullable=False,
        comment="연결된 게임 세션 ID",
    )
    round_id: Mapped[int | None] = mapped_column(
        ForeignKey("game_rounds.id", name="fk_game_chat_logs_round"),
        nullable=True,
        comment="연결된 라운드 ID (라운드제 채팅게임의 문제 단위)",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_game_chat_logs_user"),
        nullable=False,
        comment="채팅 입력 유저",
    )
    message: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="입력 메시지"
    )
    is_correct: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False, comment="정답 여부"
    )
    server_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="서버 수신 타임스탬프 (클라이언트 시간 무시)"
    )

    # --- relationships ---
    session: Mapped["GameSession"] = relationship(back_populates="chat_logs")
    user: Mapped["User"] = relationship(back_populates="chat_logs")
