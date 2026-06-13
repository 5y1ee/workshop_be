from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Buff(Base, TimestampMixin):
    __tablename__ = "buff"
    __table_args__ = (
        CheckConstraint("type IN ('buff', 'debuff')", name="buff_type_check"),
        CheckConstraint(
            "effect_type IN ('point_penalty', 'point_freeze', 'action_restrict', "
            "'steal', 'reroll', 'double', 'immunity', 'first_pick')",
            name="buff_effect_type_check",
        ),
        CheckConstraint(
            "duration IN ('instant', 'next_game', 'two_games', 'until_used')",
            name="buff_duration_check",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="카드 이름 (예: 훈민정음, 왼손잡이)"
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, comment="카드 효과 설명"
    )
    type: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="버프/디버프 구분 (buff/debuff)"
    )
    effect_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="효과 유형"
    )
    duration: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="지속 시간 (instant/next_game/two_games/until_used)",
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_buff_updated"),
        nullable=True,
        comment="최종 수정한 운영자",
    )

    # --- relationships ---
    envelopes: Mapped[list["Envelope"]] = relationship(
        back_populates="buff", foreign_keys="Envelope.buff_id"
    )
    team_buffs: Mapped[list["TeamBuff"]] = relationship(
        back_populates="buff", foreign_keys="TeamBuff.buff_id"
    )


class TeamBuff(Base, TimestampMixin):
    __tablename__ = "team_buffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", name="fk_team_buffs_team"),
        nullable=False,
        comment="대상 팀 ID",
    )
    buff_id: Mapped[int] = mapped_column(
        ForeignKey("buff.id", name="fk_team_buffs_buff"),
        nullable=False,
        comment="보유한 버프/디버프 ID",
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", name="fk_team_buffs_session"),
        nullable=False,
        comment="부여된 게임 세션 ID",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False, comment="현재 활성 여부"
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="실제 발동 시각"
    )
    expires_after: Mapped[int | None] = mapped_column(
        ForeignKey("game_sessions.id", name="fk_team_buffs_expires"),
        nullable=True,
        comment="만료되는 게임 세션 ID",
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_team_buffs_created_by"),
        nullable=False,
        comment="부여한 운영자",
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_team_buffs_updated_by"),
        nullable=True,
        comment="최종 수정한 운영자",
    )

    # --- relationships ---
    team: Mapped["Team"] = relationship(
        back_populates="team_buffs", foreign_keys=[team_id]
    )
    buff: Mapped["Buff"] = relationship(
        back_populates="team_buffs", foreign_keys=[buff_id]
    )
    session: Mapped["GameSession"] = relationship(foreign_keys=[session_id])
