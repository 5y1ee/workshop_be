"""rewards gacha fields: win_rate, is_revealed

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-06-16 23:29:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a1b2"
down_revision: Union[str, None] = "b2c3d4e5f6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "rewards",
        sa.Column(
            "win_rate",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.0"),
            comment="당첨 확률 (0.0~1.0, 5%=0.05). 관리자가 정수 퍼센트로 입력 후 /100 저장.",
        ),
    )
    op.add_column(
        "rewards",
        sa.Column(
            "is_revealed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="최초 당첨자 발생 시 true — 도감에 내용 공개",
        ),
    )


def downgrade() -> None:
    op.drop_column("rewards", "is_revealed")
    op.drop_column("rewards", "win_rate")
