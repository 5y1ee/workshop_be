"""hidden role unique user per season

Revision ID: a6b7c8d9e0f1
Revises: f6a1b2c3d4e5
Create Date: 2026-06-17 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "a6b7c8d9e0f1"
down_revision: Union[str, None] = "f6a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_user_hidden_roles_season_user",
        "user_hidden_roles",
        ["season_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_user_hidden_roles_season_user",
        "user_hidden_roles",
        type_="unique",
    )
