from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Timetable(Base, TimestampMixin):
    __tablename__ = "timetable"
    __table_args__ = (
        CheckConstraint(
            "score_mode IN ('team', 'individual')",
            name="timetable_score_mode_check",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", name="fk_timetable_season"),
        nullable=False,
        comment="소속 시즌 ID",
    )
    game_id: Mapped[int] = mapped_column(
        ForeignKey("game.id", name="fk_timetable_game"),
        nullable=False,
        comment="연결된 게임 ID",
    )
    phase: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="진행 단계 구분 (예: 저녁식사 전, 저녁식사 후, 2일차)"
    )
    order_index: Mapped[int] = mapped_column(
        nullable=False, comment="전체 진행 순서"
    )
    label: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="화면 표시용 라벨 (예: 에피타이저, 메인①)"
    )
    raffle_reward: Mapped[int] = mapped_column(
        server_default=text("0"), nullable=False, comment="라운드 종료 시 지급할 뽑기권 수"
    )
    main_visible: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
        comment="메인 화면에서 이미지와 라벨을 강조 노출할지 여부",
    )
    score_mode: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="스코어보드 집계 단위 오버라이드 (team/individual). NULL이면 게임의 participant_type 사용",
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_timetable_updated"),
        nullable=True,
        comment="최종 수정한 운영자",
    )

    # --- relationships ---
    season: Mapped["Season"] = relationship(back_populates="timetables")
    game: Mapped["Game"] = relationship(back_populates="timetables")
    sessions: Mapped[list["GameSession"]] = relationship(back_populates="timetable")
