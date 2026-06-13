from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

UserRole = Literal["admin", "user"]


class UserBase(BaseModel):
    username: str
    nickname: str
    role: UserRole


class UserCreate(UserBase):
    password: str
    team_id: int | None = None


class UserUpdate(BaseModel):
    nickname: str | None = None
    role: UserRole | None = None
    team_id: int | None = None
    point: int | None = None
    profile_image: str | None = None
    password: str | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    role: str
    team_id: int | None
    point: int
    profile_image: str | None
    created_at: datetime
    updated_at: datetime | None
