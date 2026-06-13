from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Reward(Base, TimestampMixin):
    __tablename__ = "rewards"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="상품명 (예: 신세계 상품권 5만원)"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="상품 설명"
    )
    total_count: Mapped[int] = mapped_column(nullable=False, comment="총 수량")
    image_url: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="상품 이미지 URL (도감용)"
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_rewards_updated"),
        nullable=True,
        comment="최종 수정한 운영자",
    )

    # --- relationships ---
    envelopes: Mapped[list["Envelope"]] = relationship(
        back_populates="reward", foreign_keys="Envelope.reward_id"
    )
