from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TimetableCreate(BaseModel):
    game_id: int
    order_index: int
    phase: str | None = None
    label: str | None = None
    raffle_reward: int = 0
    main_visible: bool = True


class TimetableUpdate(BaseModel):
    game_id: int | None = None
    order_index: int | None = None
    phase: str | None = None
    label: str | None = None
    raffle_reward: int | None = None
    main_visible: bool | None = None


class TimetableRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_id: int
    game_id: int
    phase: str | None
    order_index: int
    label: str | None
    raffle_reward: int
    main_visible: bool
    created_at: datetime
    updated_at: datetime | None
