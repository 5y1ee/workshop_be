from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HiddenRoleCreate(BaseModel):
    name: str
    description: str
    scope: str = "global"
    success_condition: str


class HiddenRoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    scope: str | None = None
    success_condition: str | None = None


class HiddenRoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    scope: str
    success_condition: str
    created_at: datetime
    updated_at: datetime | None


class HiddenRoleAssign(BaseModel):
    role_id: int


class HiddenRoleAssignmentRead(BaseModel):
    id: int
    season_id: int
    user_id: int
    nickname: str
    team_id: int | None
    team_name: str | None
    role_id: int
    role_name: str
    role_description: str
    success_condition: str
    is_revealed: bool
    is_success: bool | None


class MyHiddenRoleRead(BaseModel):
    id: int
    role_id: int
    name: str
    description: str
    success_condition: str
    is_revealed: bool
    is_success: bool | None
