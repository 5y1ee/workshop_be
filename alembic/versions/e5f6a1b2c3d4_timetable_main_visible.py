"""timetable main visible flag

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e5f6a1b2c3d4"
down_revision: Union[str, None] = "d4e5f6a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "timetable",
        sa.Column(
            "main_visible",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="메인 화면에서 이미지와 라벨을 강조 노출할지 여부",
        ),
    )


def downgrade() -> None:
    op.drop_column("timetable", "main_visible")
