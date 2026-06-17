"""realtime notice and song hint reveal

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-06-17 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "game_rounds",
        sa.Column(
            "hint_revealed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="chat 타입 힌트 공개 여부",
        ),
    )

    op.create_table(
        "notices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "season_id",
            sa.Integer(),
            sa.ForeignKey("seasons.id", name="fk_notices_season"),
            nullable=False,
            comment="소속 시즌 ID",
        ),
        sa.Column("message", sa.Text(), nullable=False, comment="공지 내용"),
        sa.Column("expires_at", sa.DateTime(), nullable=False, comment="공지 만료 시각"),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_notices_created_by"),
            nullable=False,
            comment="공지 생성 운영자",
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="공지 삭제 시각"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="생성 시각",
        ),
    )
    op.create_index("ix_notices_season_expires", "notices", ["season_id", "expires_at"])


def downgrade() -> None:
    op.drop_index("ix_notices_season_expires", table_name="notices")
    op.drop_table("notices")
    op.drop_column("game_rounds", "hint_revealed")
