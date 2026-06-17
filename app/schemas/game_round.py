from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

RoundStatus = Literal["waiting", "open", "closed"]
TapMode = Literal["count", "speed", "timing"]


class RoundCreate(BaseModel):
    order_index: int
    prompt: str | None = None
    media_url: str | None = None
    options: list[str] | None = None
    correct_answer: str | None = None
    tap_mode: TapMode | None = None
    duration: int | None = None
    target_time: float | None = None


class RoundUpdate(BaseModel):
    prompt: str | None = None
    media_url: str | None = None
    options: list[str] | None = None
    correct_answer: str | None = None
    tap_mode: TapMode | None = None
    duration: int | None = None
    target_time: float | None = None


class RoundRead(BaseModel):
    """플레이어용 응답. 정답(correct_answer)은 공개 전 비노출."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    order_index: int
    status: str
    prompt: str | None
    media_url: str | None
    options: list[str] | None
    hint_revealed: bool
    opened_at: datetime | None
    closed_at: datetime | None
    tap_mode: str | None
    duration: int | None
    target_time: float | None
    signal_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class TapResult(BaseModel):
    """tap 게임 결과 항목 (모드별 value 의미: count=횟수, speed=반응ms, timing=편차초)."""

    user_id: int
    nickname: str
    team_id: int | None
    team_name: str | None
    value: float
    rank: int


class RoundReveal(BaseModel):
    """라운드 마감 후 정답 + 제출 분포 공개 (운영자/리뷰용)."""

    round_id: int
    correct_answer: str | None
    total_submissions: int
    distribution: dict[str, int]


class SubmissionResult(BaseModel):
    """제출 직후 응답. 공정성을 위해 정답 여부는 마감 전까지 비노출."""

    round_id: int
    accepted: bool


class ChatLogRead(BaseModel):
    """운영자용 채팅 로그. 정답 여부는 참가자 응답에는 노출하지 않는다."""

    id: int
    session_id: int
    round_id: int | None
    user_id: int
    nickname: str
    team_id: int | None
    team_name: str | None
    message: str
    is_correct: bool
    server_time: datetime
