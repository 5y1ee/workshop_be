from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ParticipantType = Literal["team_vs", "individual", "team_internal", "representative"]
InputType = Literal["chat", "button", "offline", "puzzle", "vote"]


class GameCreate(BaseModel):
    title: str
    description: str | None = None
    participant_type: ParticipantType
    input_type: InputType


class GameUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    participant_type: ParticipantType | None = None
    input_type: InputType | None = None


class GameRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    participant_type: str
    input_type: str
    created_at: datetime
    updated_at: datetime | None
