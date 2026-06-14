from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RewardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    total_count: int
    image_url: str | None
    created_at: datetime
    updated_at: datetime | None
