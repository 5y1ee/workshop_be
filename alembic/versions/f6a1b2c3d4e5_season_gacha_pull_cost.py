"""season gacha pull cost

Revision ID: f6a1b2c3d4e5
Revises: e5f6a1b2c3d4
Create Date: 2026-06-17 00:00:01.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f6a1b2c3d4e5"
down_revision: Union[str, None] = "e5f6a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "seasons",
        sa.Column(
            "gacha_pull_cost",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
            comment="뽑기 1회 차감 포인트",
        ),
    )


def downgrade() -> None:
    op.drop_column("seasons", "gacha_pull_cost")
