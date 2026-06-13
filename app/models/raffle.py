from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin


class RaffleTicket(Base, CreatedAtMixin):
    __tablename__ = "raffle_tickets"
    __table_args__ = (
        CheckConstraint(
            "owner_type IN ('team', 'user')", name="raffle_tickets_owner_type_check"
        ),
        CheckConstraint(
            "action IN ('earned', 'used', 'lost')",
            name="raffle_tickets_action_check",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("game_sessions.id", name="fk_raffle_tickets_session"),
        nullable=True,
        comment="관련 게임 세션 ID (운영자 직접 부여 시 NULL)",
    )
    owner_type: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="뽑기권 소유 단위 (team/user)"
    )
    owner_id: Mapped[int] = mapped_column(
        nullable=False, comment="owner_type에 따라 teams.id 또는 users.id"
    )
    action: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="획득/사용/몰수 (earned/used/lost)"
    )
    amount: Mapped[int] = mapped_column(nullable=False, comment="변동 수량")
    reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="사유 (예: 게임보상, 도박승리, 운영자부여, 봉투뽑기)",
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_raffle_tickets_created_by"),
        nullable=False,
        comment="기록한 운영자 또는 시스템",
    )

    # --- relationships ---
    session: Mapped["GameSession | None"] = relationship(
        back_populates="raffle_tickets"
    )
