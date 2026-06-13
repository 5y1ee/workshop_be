from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TeamCreate(BaseModel):
    name: str


class TeamUpdate(BaseModel):
    name: str


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_id: int
    name: str
    created_at: datetime
