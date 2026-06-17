"""timetable score_mode override (team / individual)

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-06-17 00:00:04.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "timetable",
        sa.Column(
            "score_mode",
            sa.String(length=20),
            nullable=True,
            comment="스코어보드 집계 단위 오버라이드 (team/individual). NULL이면 게임의 participant_type 사용",
        ),
    )
    op.create_check_constraint(
        "timetable_score_mode_check",
        "timetable",
        "score_mode IN ('team', 'individual')",
    )


def downgrade() -> None:
    op.drop_constraint("timetable_score_mode_check", "timetable", type_="check")
    op.drop_column("timetable", "score_mode")
