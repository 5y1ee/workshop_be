from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RewardClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reward_id: int
    user_id: int
    claimed_at: datetime
    created_by: int


class RewardClaimDetail(BaseModel):
    """관리자용 — 수령자 닉네임 포함."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    reward_id: int
    user_id: int
    nickname: str
    claimed_at: datetime


class RewardReadWithClaims(BaseModel):
    """도감 목록용 — 수령 현황 포함."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    season_id: int
    name: str
    description: str | None
    total_count: int
    image_url: str | None
    win_rate: float
    is_revealed: bool
    claimed_count: int
    remaining_count: int
    my_claimed: bool
