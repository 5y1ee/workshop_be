from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RewardCreate(BaseModel):
    name: str
    description: str | None = None
    total_count: int = 1
    image_url: str | None = None
    win_rate_pct: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="당첨 확률 (퍼센트, 0~100). 예: 5 → 5%",
    )

    @field_validator("win_rate_pct")
    @classmethod
    def round_rate(cls, v: float) -> float:
        return round(v, 2)


class RewardUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    total_count: int | None = None
    image_url: str | None = None
    win_rate_pct: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="당첨 확률 (퍼센트, 0~100)",
    )

    @field_validator("win_rate_pct")
    @classmethod
    def round_rate(cls, v: float | None) -> float | None:
        return round(v, 2) if v is not None else None


class RewardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_id: int
    name: str
    description: str | None
    total_count: int
    image_url: str | None
    win_rate: float
    is_revealed: bool
    created_at: datetime
    updated_at: datetime | None
