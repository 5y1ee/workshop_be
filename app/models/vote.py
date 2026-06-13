from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin


class VoteItem(Base, TimestampMixin):
    __tablename__ = "vote_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="투표 항목 이름 (예: MVP, MUVP, 트롤러)"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="투표 항목 설명"
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_vote_items_updated"),
        nullable=True,
        comment="최종 수정한 운영자",
    )

    # --- relationships ---
    ballots: Mapped[list["VoteBallot"]] = relationship(back_populates="vote_item")


class VoteBallot(Base, TimestampMixin):
    __tablename__ = "vote_ballots"
    __table_args__ = (
        CheckConstraint(
            "status IN ('waiting', 'open', 'closed')",
            name="vote_ballots_status_check",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", name="fk_vote_ballots_season"),
        nullable=False,
        comment="소속 시즌 ID",
    )
    vote_item_id: Mapped[int] = mapped_column(
        ForeignKey("vote_items.id", name="fk_vote_ballots_vote_item"),
        nullable=False,
        comment="투표 항목 ID",
    )
    status: Mapped[str] = mapped_column(
        String(10),
        server_default=text("'waiting'"),
        nullable=False,
        comment="투표 상태 (waiting/open/closed)",
    )
    order_index: Mapped[int] = mapped_column(nullable=False, comment="투표 진행 순서")
    opened_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="투표 시작 시각"
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="투표 종료 시각"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_vote_ballots_created_by"),
        nullable=False,
        comment="생성한 운영자",
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_vote_ballots_updated_by"),
        nullable=True,
        comment="최종 수정한 운영자",
    )

    # --- relationships ---
    season: Mapped["Season"] = relationship(back_populates="vote_ballots")
    vote_item: Mapped["VoteItem"] = relationship(back_populates="ballots")
    records: Mapped[list["VoteRecord"]] = relationship(back_populates="ballot")


class VoteRecord(Base, CreatedAtMixin):
    __tablename__ = "vote_records"
    __table_args__ = (
        UniqueConstraint(
            "ballot_id", "voter_id", name="uq_vote_records_ballot_voter"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ballot_id: Mapped[int] = mapped_column(
        ForeignKey("vote_ballots.id", name="fk_vote_records_ballot"),
        nullable=False,
        comment="연결된 투표지 ID",
    )
    voter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_vote_records_voter"),
        nullable=False,
        comment="투표한 유저 ID",
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_vote_records_target"),
        nullable=False,
        comment="투표 대상 유저 ID",
    )

    # --- relationships ---
    ballot: Mapped["VoteBallot"] = relationship(back_populates="records")
