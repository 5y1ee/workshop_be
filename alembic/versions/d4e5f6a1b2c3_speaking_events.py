"""speaking events

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-06-17 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a1b2c3"
down_revision: Union[str, None] = "c3d4e5f6a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "speaking_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "season_id",
            sa.Integer(),
            sa.ForeignKey("seasons.id", name="fk_speaking_events_season"),
            nullable=False,
            comment="소속 시즌 ID",
        ),
        sa.Column("mode", sa.String(10), nullable=False, comment="발언권 이벤트 모드"),
        sa.Column(
            "status",
            sa.String(10),
            server_default=sa.text("'open'"),
            nullable=False,
            comment="이벤트 상태",
        ),
        sa.Column("duration", sa.Integer(), nullable=True, comment="count 제한 시간"),
        sa.Column("target_time", sa.Float(), nullable=True, comment="timing 목표 시간"),
        sa.Column("opened_at", sa.DateTime(), nullable=False, comment="이벤트 시작 시각"),
        sa.Column("closed_at", sa.DateTime(), nullable=True, comment="이벤트 마감 시각"),
        sa.Column("signal_at", sa.DateTime(), nullable=True, comment="speed 신호 시각"),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_speaking_events_created_by"),
            nullable=False,
            comment="이벤트 생성 운영자",
        ),
        sa.Column(
            "updated_by",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_speaking_events_updated_by"),
            nullable=True,
            comment="이벤트 수정 운영자",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=True,
            comment="최종 수정 시각",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="생성 시각",
        ),
        sa.CheckConstraint(
            "mode IN ('count', 'speed', 'timing')",
            name="speaking_events_mode_check",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'closed')",
            name="speaking_events_status_check",
        ),
    )
    op.create_index(
        "uq_speaking_events_one_open_per_season",
        "speaking_events",
        ["season_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )

    op.create_table(
        "speaking_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("speaking_events.id", name="fk_speaking_submissions_event"),
            nullable=False,
            comment="연결된 발언권 이벤트 ID",
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_speaking_submissions_user"),
            nullable=False,
            comment="제출 유저 ID",
        ),
        sa.Column("value", sa.Float(), nullable=False, comment="제출 기록"),
        sa.Column("server_time", sa.DateTime(), nullable=False, comment="서버 수신 시각"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="생성 시각",
        ),
        sa.UniqueConstraint(
            "event_id", "user_id", name="uq_speaking_submissions_event_user"
        ),
    )

    op.create_table(
        "speaking_tap_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("speaking_events.id", name="fk_speaking_tap_logs_event"),
            nullable=False,
            comment="연결된 발언권 이벤트 ID",
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_speaking_tap_logs_user"),
            nullable=False,
            comment="탭한 유저 ID",
        ),
        sa.Column("server_time", sa.DateTime(), nullable=False, comment="서버 수신 시각"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="생성 시각",
        ),
    )

    op.create_table(
        "speaking_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("speaking_events.id", name="fk_speaking_grants_event"),
            nullable=False,
            comment="연결된 발언권 이벤트 ID",
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_speaking_grants_user"),
            nullable=False,
            comment="발언권을 받은 유저 ID",
        ),
        sa.Column("rank", sa.Integer(), nullable=False, comment="결과 순위"),
        sa.Column("value", sa.Float(), nullable=False, comment="결과 기록"),
        sa.Column(
            "granted_by",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_speaking_grants_granted_by"),
            nullable=False,
            comment="발언권 부여 운영자",
        ),
        sa.Column("granted_at", sa.DateTime(), nullable=False, comment="발언권 부여 시각"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="생성 시각",
        ),
        sa.UniqueConstraint("event_id", "user_id", name="uq_speaking_grants_event_user"),
    )


def downgrade() -> None:
    op.drop_table("speaking_grants")
    op.drop_table("speaking_tap_logs")
    op.drop_table("speaking_submissions")
    op.drop_index(
        "uq_speaking_events_one_open_per_season",
        table_name="speaking_events",
    )
    op.drop_table("speaking_events")
