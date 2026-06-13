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


class HiddenRole(Base, TimestampMixin):
    __tablename__ = "hidden_roles"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('team', 'global')", name="hidden_roles_scope_check"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="역할 이름 (예: 사대주의자, 바람잡이)"
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, comment="역할 설명 및 미션 내용"
    )
    scope: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="역할 범위 (team/global)"
    )
    success_condition: Mapped[str] = mapped_column(
        Text, nullable=False, comment="성공 판정 기준"
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_hidden_roles_updated"),
        nullable=True,
        comment="최종 수정한 운영자",
    )

    # --- relationships ---
    assignments: Mapped[list["UserHiddenRole"]] = relationship(back_populates="role")


class UserHiddenRole(Base, TimestampMixin):
    __tablename__ = "user_hidden_roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", name="fk_user_hidden_roles_season"),
        nullable=False,
        comment="소속 시즌 ID",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_user_hidden_roles_user"),
        nullable=False,
        comment="역할 배분된 유저 ID",
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("hidden_roles.id", name="fk_user_hidden_roles_role"),
        nullable=False,
        comment="배분된 역할 ID",
    )
    is_revealed: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
        comment="공개 여부 (시상식 전까지 FALSE)",
    )
    is_success: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, comment="미션 성공 여부 (NULL=미판정)"
    )
    judged_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_user_hidden_roles_judged_by"),
        nullable=True,
        comment="판정한 운영자",
    )
    judged_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="판정 시각"
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_user_hidden_roles_updated"),
        nullable=True,
        comment="최종 수정한 운영자",
    )

    # --- relationships ---
    season: Mapped["Season"] = relationship(back_populates="user_hidden_roles")
    role: Mapped["HiddenRole"] = relationship(back_populates="assignments")
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
