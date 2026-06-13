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

from app.db.base import Base, TimestampMixin


class Envelope(Base, TimestampMixin):
    __tablename__ = "envelopes"
    __table_args__ = (
        CheckConstraint(
            "content_type IN ('reward', 'blank')",
            name="envelopes_content_type_check",
        ),
        CheckConstraint(
            "owner_type IN ('team', 'user')", name="envelopes_owner_type_check"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", name="fk_envelopes_session"),
        nullable=False,
        comment="발행된 게임 세션 ID",
    )
    number: Mapped[int] = mapped_column(nullable=False, comment="봉투 번호")
    content_type: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="봉투 내용물 유형 (reward/blank)"
    )
    reward_id: Mapped[int | None] = mapped_column(
        ForeignKey("rewards.id", name="fk_envelopes_reward"),
        nullable=True,
        comment="내용물이 상품일 때 rewards.id",
    )
    buff_id: Mapped[int | None] = mapped_column(
        ForeignKey("buff.id", name="fk_envelopes_buff"),
        nullable=True,
        comment="꽝 봉투에 동봉된 버프/디버프 카드 ID",
    )
    owner_type: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="봉투 소유 단위 (team/user)"
    )
    owner_id: Mapped[int | None] = mapped_column(
        nullable=True, comment="owner_type에 따라 teams.id 또는 users.id"
    )
    is_opened: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False, comment="개봉 여부"
    )
    opened_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="개봉 시각"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_envelopes_created_by"),
        nullable=False,
        comment="봉투 생성한 운영자",
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_envelopes_updated_by"),
        nullable=True,
        comment="최종 수정한 운영자",
    )

    # --- relationships ---
    session: Mapped["GameSession"] = relationship(
        back_populates="envelopes", foreign_keys=[session_id]
    )
    reward: Mapped["Reward | None"] = relationship(
        back_populates="envelopes", foreign_keys=[reward_id]
    )
    buff: Mapped["Buff | None"] = relationship(
        back_populates="envelopes", foreign_keys=[buff_id]
    )
