from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Season(Base, TimestampMixin):
    __tablename__ = "seasons"
    __table_args__ = (
        CheckConstraint(
            "status IN ('preparing', 'active', 'done')", name="seasons_status_check"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="시즌 이름 (예: 2026 가평 워크샵, 리허설)"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'preparing'"),
        nullable=False,
        comment="시즌 상태 (preparing/active/done)",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="시즌 시작 시각"
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="시즌 종료 시각"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_seasons_created"),
        nullable=False,
        comment="시즌 생성한 운영자",
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_seasons_updated"),
        nullable=True,
        comment="최종 수정한 운영자",
    )

    # --- relationships ---
    teams: Mapped[list["Team"]] = relationship(back_populates="season")
    timetables: Mapped[list["Timetable"]] = relationship(back_populates="season")
    vote_ballots: Mapped[list["VoteBallot"]] = relationship(back_populates="season")
    user_hidden_roles: Mapped[list["UserHiddenRole"]] = relationship(
        back_populates="season"
    )
