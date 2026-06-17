from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BuffCreate(BaseModel):
    name: str
    description: str
    type: str
    effect_type: str = "action_restrict"
    duration: str = "next_game"


class BuffUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    type: str | None = None
    effect_type: str | None = None
    duration: str | None = None


class BuffRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    type: str
    effect_type: str
    duration: str
    created_at: datetime
    updated_at: datetime | None


class TeamBuffCreate(BaseModel):
    team_id: int
    buff_id: int


class TeamBuffRead(BaseModel):
    id: int
    team_id: int
    team_name: str
    buff_id: int
    buff_name: str
    buff_description: str
    buff_type: str
    effect_type: str
    duration: str
    session_id: int
    session_state: str
    is_active: bool
    activated_at: datetime | None
