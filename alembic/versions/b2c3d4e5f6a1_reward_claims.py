"""reward claims table

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-06-16 23:05:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a1"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reward_claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "reward_id",
            sa.Integer(),
            sa.ForeignKey("rewards.id", name="fk_reward_claims_reward"),
            nullable=False,
            comment="수령한 리워드 ID",
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_reward_claims_user"),
            nullable=False,
            comment="수령한 유저 ID",
        ),
        sa.Column(
            "claimed_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="수령 처리 시각",
        ),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_reward_claims_created_by"),
            nullable=False,
            comment="기록한 운영자 ID",
        ),
        sa.UniqueConstraint("reward_id", "user_id", name="uq_reward_claims_user"),
    )


def downgrade() -> None:
    op.drop_table("reward_claims")
