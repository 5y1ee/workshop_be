from sqlalchemy import CheckConstraint, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'user')", name="users_role_check"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="로그인 ID"
    )
    password: Mapped[str] = mapped_column(String(255), nullable=False, comment="비밀번호")
    nickname: Mapped[str] = mapped_column(String(50), nullable=False, comment="화면 표시 이름")
    role: Mapped[str] = mapped_column(String(10), nullable=False, comment="권한 (admin/user)")
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", name="fk_users_team"),
        nullable=True,
        comment="소속 팀 ID (팀 빌딩 전 NULL)",
    )
    point: Mapped[int] = mapped_column(
        server_default=text("0"), nullable=False, comment="개인 누적 포인트"
    )
    profile_image: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="프로필 이미지 URL"
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_users_updated"),
        nullable=True,
        comment="최종 수정한 운영자",
    )

    # --- relationships ---
    team: Mapped["Team | None"] = relationship(
        back_populates="members", foreign_keys=[team_id]
    )
    chat_logs: Mapped[list["GameChatLog"]] = relationship(back_populates="user")
