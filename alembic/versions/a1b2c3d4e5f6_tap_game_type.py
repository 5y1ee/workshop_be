"""tap game type

Revision ID: a1b2c3d4e5f6
Revises: 9c4a1f2e8b71
Create Date: 2026-06-16 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9c4a1f2e8b71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # game_rounds: tap 전용 컬럼 추가
    op.add_column(
        "game_rounds",
        sa.Column("tap_mode", sa.String(10), nullable=True,
                  comment="tap 게임 모드 (count/speed/timing)"),
    )
    op.add_column(
        "game_rounds",
        sa.Column("duration", sa.Integer(), nullable=True,
                  comment="tap count 모드 타이머(초)"),
    )
    op.add_column(
        "game_rounds",
        sa.Column("target_time", sa.Float(), nullable=True,
                  comment="tap timing 모드 목표 시간(초, 0.1 단위)"),
    )
    op.add_column(
        "game_rounds",
        sa.Column("signal_at", sa.DateTime(), nullable=True,
                  comment="tap speed 모드 신호 발사 시각"),
    )
    op.create_check_constraint(
        "game_rounds_tap_mode_check",
        "game_rounds",
        "tap_mode IS NULL OR tap_mode IN ('count', 'speed', 'timing')",
    )

    # tap_logs 테이블 생성
    op.create_table(
        "tap_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("round_id", sa.Integer(),
                  sa.ForeignKey("game_rounds.id", name="fk_tap_logs_round"),
                  nullable=False, comment="연결된 라운드 ID"),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", name="fk_tap_logs_user"),
                  nullable=False, comment="탭한 유저 ID"),
        sa.Column("server_time", sa.DateTime(), nullable=False,
                  comment="서버 수신 타임스탬프"),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # game.input_type CHECK 제약 업데이트 ('tap' 추가)
    with op.batch_alter_table("game") as batch_op:
        batch_op.drop_constraint("game_input_type_check", type_="check")
        batch_op.create_check_constraint(
            "game_input_type_check",
            "input_type IN ('chat', 'button', 'offline', 'puzzle', 'vote', 'tap')",
        )


def downgrade() -> None:
    with op.batch_alter_table("game") as batch_op:
        batch_op.drop_constraint("game_input_type_check", type_="check")
        batch_op.create_check_constraint(
            "game_input_type_check",
            "input_type IN ('chat', 'button', 'offline', 'puzzle', 'vote')",
        )

    op.drop_table("tap_logs")

    op.drop_constraint("game_rounds_tap_mode_check", "game_rounds", type_="check")
    op.drop_column("game_rounds", "signal_at")
    op.drop_column("game_rounds", "target_time")
    op.drop_column("game_rounds", "duration")
    op.drop_column("game_rounds", "tap_mode")
