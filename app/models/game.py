from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Game(Base, TimestampMixin):
    __tablename__ = "game"
    __table_args__ = (
        CheckConstraint(
            "participant_type IN ('team_vs', 'individual', 'team_internal', 'representative')",
            name="game_participant_type_check",
        ),
        CheckConstraint(
            "input_type IN ('chat', 'button', 'offline', 'puzzle', 'vote')",
            name="game_input_type_check",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="게임 이름 (예: 노래맞추기, 거짓말 탐지기)"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="게임 설명 (툴팁 표시용)"
    )
    participant_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="참여 단위 (team_vs/individual/team_internal/representative)",
    )
    input_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="참여 방식 (chat/button/offline/puzzle/vote)"
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_game_updated"),
        nullable=True,
        comment="최종 수정한 운영자",
    )

    # --- relationships ---
    timetables: Mapped[list["Timetable"]] = relationship(back_populates="game")
