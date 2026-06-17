"""offline game catalog entries (team / individual)

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-06-17 00:00:03.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "a6b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO game (title, description, participant_type, input_type)
        SELECT '팀 오프라인 게임', '오프라인 진행 · 팀별 점수 수동 기록', 'team_vs', 'offline'
        WHERE NOT EXISTS (SELECT 1 FROM game WHERE title = '팀 오프라인 게임')
        """
    )
    op.execute(
        """
        INSERT INTO game (title, description, participant_type, input_type)
        SELECT '개인 오프라인 게임', '오프라인 진행 · 개인별 점수 수동 기록', 'individual', 'offline'
        WHERE NOT EXISTS (SELECT 1 FROM game WHERE title = '개인 오프라인 게임')
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM game WHERE title IN ('팀 오프라인 게임', '개인 오프라인 게임')"
    )
