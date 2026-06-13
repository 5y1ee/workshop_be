from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin


class Team(Base, CreatedAtMixin):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", name="fk_teams_season"),
        nullable=False,
        comment="소속 시즌 ID",
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="팀 이름")

    # --- relationships ---
    season: Mapped["Season"] = relationship(back_populates="teams")
    members: Mapped[list["User"]] = relationship(
        back_populates="team", foreign_keys="User.team_id"
    )
    team_buffs: Mapped[list["TeamBuff"]] = relationship(back_populates="team")
