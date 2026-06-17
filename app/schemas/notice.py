from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NoticeCreate(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    duration_minutes: int = Field(default=10, ge=1, le=1440)


class NoticeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_id: int
    message: str
    expires_at: datetime
    created_by: int
    deleted_at: datetime | None
    created_at: datetime


class CurrentNoticeRead(BaseModel):
    notice: NoticeRead | None
