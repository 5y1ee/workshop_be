"""score chat log link

Revision ID: 9c4a1f2e8b71
Revises: 42fcf93c2c97
Create Date: 2026-06-16 13:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c4a1f2e8b71"
down_revision: Union[str, None] = "42fcf93c2c97"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "game_score_logs",
        sa.Column(
            "chat_log_id",
            sa.Integer(),
            nullable=True,
            comment="노래맞추기 정답 후보 채팅 로그 ID",
        ),
    )
    op.create_foreign_key(
        "fk_game_score_logs_chat_log",
        "game_score_logs",
        "game_chat_logs",
        ["chat_log_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_game_score_logs_chat_log_id",
        "game_score_logs",
        ["chat_log_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_game_score_logs_chat_log_id", "game_score_logs", type_="unique"
    )
    op.drop_constraint(
        "fk_game_score_logs_chat_log", "game_score_logs", type_="foreignkey"
    )
    op.drop_column("game_score_logs", "chat_log_id")
