from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

SpeakingMode = Literal["count", "speed", "timing"]


class SpeakingEventCreate(BaseModel):
    mode: SpeakingMode
    duration: int | None = None
    target_time: float | None = None


class SpeakingEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_id: int
    mode: str
    status: str
    duration: int | None
    target_time: float | None
    opened_at: datetime
    closed_at: datetime | None
    signal_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class SpeakingResult(BaseModel):
    user_id: int
    nickname: str
    team_id: int | None
    team_name: str | None
    value: float
    rank: int
    granted: bool = False


class SpeakingEventResults(BaseModel):
    event: SpeakingEventRead
    results: list[SpeakingResult]


class SpeakingGrantCreate(BaseModel):
    user_id: int


class SpeakingGrantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    user_id: int
    rank: int
    value: float
    granted_by: int
    granted_at: datetime
    created_at: datetime
