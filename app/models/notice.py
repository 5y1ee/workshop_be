"""시즌별 실시간 공지 모델."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin


class Notice(Base, CreatedAtMixin):
    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", name="fk_notices_season"),
        nullable=False,
        comment="소속 시즌 ID",
    )
    message: Mapped[str] = mapped_column(Text, nullable=False, comment="공지 내용")
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="공지 만료 시각"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_notices_created_by"),
        nullable=False,
        comment="공지 생성 운영자",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="공지 삭제 시각"
    )
