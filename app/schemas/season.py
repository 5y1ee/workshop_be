from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

SeasonStatus = Literal["preparing", "active", "done"]


class SeasonCreate(BaseModel):
    name: str


class SeasonUpdate(BaseModel):
    name: str | None = None
    status: SeasonStatus | None = None


class SeasonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    created_by: int
    updated_by: int | None
    created_at: datetime
    updated_at: datetime | None
