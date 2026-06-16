from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RewardClaim(Base):
    __tablename__ = "reward_claims"
    __table_args__ = (
        UniqueConstraint("reward_id", "user_id", name="uq_reward_claims_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reward_id: Mapped[int] = mapped_column(
        ForeignKey("rewards.id", name="fk_reward_claims_reward"),
        nullable=False,
        comment="수령한 리워드 ID",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_reward_claims_user"),
        nullable=False,
        comment="수령한 유저 ID",
    )
    claimed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
        comment="수령 처리 시각",
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_reward_claims_created_by"),
        nullable=False,
        comment="기록한 운영자 ID",
    )

    # --- relationships ---
    reward: Mapped["Reward"] = relationship(  # noqa: F821
        foreign_keys=[reward_id],
    )
    user: Mapped["User"] = relationship(  # noqa: F821
        foreign_keys=[user_id],
    )
