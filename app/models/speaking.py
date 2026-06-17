"""전역 발언권 이벤트 모델.

게임 세션 점수와 분리된 운영자 주도 이벤트다. 기존 tap 게임과 같은
count/speed/timing 방식을 쓰지만, 결과는 발언권 지급 기록으로만 남긴다.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin


class SpeakingEvent(Base, TimestampMixin):
    __tablename__ = "speaking_events"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('count', 'speed', 'timing')",
            name="speaking_events_mode_check",
        ),
        CheckConstraint(
            "status IN ('open', 'closed')",
            name="speaking_events_status_check",
        ),
        Index(
            "uq_speaking_events_one_open_per_season",
            "season_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", name="fk_speaking_events_season"),
        nullable=False,
        comment="소속 시즌 ID",
    )
    mode: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="발언권 이벤트 모드 (count/speed/timing)"
    )
    status: Mapped[str] = mapped_column(
        String(10),
        server_default=text("'open'"),
        nullable=False,
        comment="이벤트 상태 (open/closed)",
    )
    duration: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="count 모드 제한 시간(초)"
    )
    target_time: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="timing 모드 목표 시간(초)"
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="이벤트 시작 시각"
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="이벤트 마감 시각"
    )
    signal_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="speed 모드 신호 발사 시각"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_speaking_events_created_by"),
        nullable=False,
        comment="이벤트 생성 운영자",
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_speaking_events_updated_by"),
        nullable=True,
        comment="이벤트 수정 운영자",
    )

    submissions: Mapped[list["SpeakingSubmission"]] = relationship(
        back_populates="event"
    )
    tap_logs: Mapped[list["SpeakingTapLog"]] = relationship(back_populates="event")
    grants: Mapped[list["SpeakingGrant"]] = relationship(back_populates="event")


class SpeakingSubmission(Base, CreatedAtMixin):
    __tablename__ = "speaking_submissions"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "user_id", name="uq_speaking_submissions_event_user"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("speaking_events.id", name="fk_speaking_submissions_event"),
        nullable=False,
        comment="연결된 발언권 이벤트 ID",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_speaking_submissions_user"),
        nullable=False,
        comment="제출 유저 ID",
    )
    value: Mapped[float] = mapped_column(
        Float, nullable=False, comment="speed=반응 ms, timing=누른 초"
    )
    server_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="서버 수신 시각"
    )

    event: Mapped["SpeakingEvent"] = relationship(back_populates="submissions")


class SpeakingTapLog(Base, CreatedAtMixin):
    __tablename__ = "speaking_tap_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("speaking_events.id", name="fk_speaking_tap_logs_event"),
        nullable=False,
        comment="연결된 발언권 이벤트 ID",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_speaking_tap_logs_user"),
        nullable=False,
        comment="탭한 유저 ID",
    )
    server_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="서버 수신 시각"
    )

    event: Mapped["SpeakingEvent"] = relationship(back_populates="tap_logs")


class SpeakingGrant(Base, CreatedAtMixin):
    __tablename__ = "speaking_grants"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_speaking_grants_event_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("speaking_events.id", name="fk_speaking_grants_event"),
        nullable=False,
        comment="연결된 발언권 이벤트 ID",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_speaking_grants_user"),
        nullable=False,
        comment="발언권을 받은 유저 ID",
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False, comment="결과 순위")
    value: Mapped[float] = mapped_column(Float, nullable=False, comment="결과 기록")
    granted_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_speaking_grants_granted_by"),
        nullable=False,
        comment="발언권을 부여한 운영자",
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="발언권 부여 시각"
    )

    event: Mapped["SpeakingEvent"] = relationship(back_populates="grants")
