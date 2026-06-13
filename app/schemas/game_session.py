from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

GameState = Literal["idle", "ready", "in_progress", "scoring", "reward", "done"]


class SessionTransition(BaseModel):
    to: GameState


class GameSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timetable_id: int
    state: str
    # 주의: seed 는 결과 예측 악용 방지를 위해 응답에 포함하지 않는다.
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
