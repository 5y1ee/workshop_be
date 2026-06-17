from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SeasonStatus = Literal["preparing", "active", "done"]


class SeasonCreate(BaseModel):
    name: str


class SeasonUpdate(BaseModel):
    name: str | None = None
    status: SeasonStatus | None = None
    gacha_pull_cost: int | None = Field(default=None, ge=1)


class SeasonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: str
    gacha_pull_cost: int
    started_at: datetime | None
    ended_at: datetime | None
    created_by: int
    updated_by: int | None
    created_at: datetime
    updated_at: datetime | None
