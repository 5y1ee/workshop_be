from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

SubjectType = Literal["team", "user"]


class ScoreCreate(BaseModel):
    subject_type: SubjectType
    subject_id: int
    score: int = 0
    memo: str | None = None


class ScoreUpdate(BaseModel):
    score: int | None = None
    memo: str | None = None


class ScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    subject_type: str
    subject_id: int
    score: int
    memo: str | None
    created_by: int
    created_at: datetime
    updated_at: datetime | None


class ScoreSummaryItem(BaseModel):
    subject_type: str
    subject_id: int
    total_score: int


class TeamScoreboardItem(BaseModel):
    team_id: int
    name: str
    total_score: int
