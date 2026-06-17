from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.models.hidden_role import HiddenRole, UserHiddenRole
from app.models.team import Team
from app.models.team_member import TeamMembership
from app.models.user import User
from app.schemas.hidden_role import (
    HiddenRoleAssign,
    HiddenRoleAssignmentRead,
    HiddenRoleCreate,
    HiddenRoleRead,
    HiddenRoleUpdate,
    MyHiddenRoleRead,
)
from app.websocket import events as ws_events

router = APIRouter(tags=["hidden-roles"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _role_or_404(db: AsyncSession, role_id: int) -> HiddenRole:
    role = await db.get(HiddenRole, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="히든롤을 찾을 수 없습니다.")
    return role


@router.get("/hidden-roles", response_model=list[HiddenRoleRead])
async def list_hidden_roles(db: DbSession, user: CurrentUser) -> list[HiddenRole]:
    result = await db.execute(select(HiddenRole).order_by(HiddenRole.id))
    return list(result.scalars().all())


@router.post("/hidden-roles", response_model=HiddenRoleRead, status_code=201)
async def create_hidden_role(
    payload: HiddenRoleCreate, db: DbSession, admin: AdminUser
) -> HiddenRole:
    role = HiddenRole(**payload.model_dump(), updated_by=admin.id)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    await ws_events.broadcast_hidden_role_changed(None, None, "created")
    return role


@router.patch("/hidden-roles/{role_id}", response_model=HiddenRoleRead)
async def update_hidden_role(
    role_id: int, payload: HiddenRoleUpdate, db: DbSession, admin: AdminUser
) -> HiddenRole:
    role = await _role_or_404(db, role_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(role, key, value)
    role.updated_by = admin.id
    role.updated_at = _utcnow()
    await db.commit()
    await db.refresh(role)
    await ws_events.broadcast_hidden_role_changed(None, None, "updated")
    return role


@router.delete("/hidden-roles/{role_id}", status_code=204)
async def delete_hidden_role(role_id: int, db: DbSession, admin: AdminUser) -> None:
    role = await _role_or_404(db, role_id)
    await db.execute(delete(UserHiddenRole).where(UserHiddenRole.role_id == role_id))
    await db.delete(role)
    await db.commit()
    await ws_events.broadcast_hidden_role_changed(None, None, "deleted")


@router.get(
    "/seasons/{season_id}/hidden-role-assignments",
    response_model=list[HiddenRoleAssignmentRead],
)
async def list_assignments(
    season_id: int, db: DbSession, admin: AdminUser
) -> list[dict]:
    result = await db.execute(
        select(
            UserHiddenRole.id,
            UserHiddenRole.season_id,
            UserHiddenRole.user_id,
            User.nickname,
            Team.id.label("team_id"),
            Team.name.label("team_name"),
            HiddenRole.id.label("role_id"),
            HiddenRole.name.label("role_name"),
            HiddenRole.description.label("role_description"),
            HiddenRole.success_condition,
            UserHiddenRole.is_revealed,
            UserHiddenRole.is_success,
        )
        .join(User, User.id == UserHiddenRole.user_id)
        .join(HiddenRole, HiddenRole.id == UserHiddenRole.role_id)
        .outerjoin(
            TeamMembership,
            and_(
                TeamMembership.season_id == UserHiddenRole.season_id,
                TeamMembership.user_id == UserHiddenRole.user_id,
            ),
        )
        .outerjoin(Team, Team.id == TeamMembership.team_id)
        .where(UserHiddenRole.season_id == season_id)
        .order_by(Team.id.nulls_last(), User.id)
    )
    return [dict(row._mapping) for row in result.all()]


@router.put(
    "/seasons/{season_id}/users/{user_id}/hidden-role",
    response_model=HiddenRoleAssignmentRead,
)
async def assign_hidden_role(
    season_id: int,
    user_id: int,
    payload: HiddenRoleAssign,
    db: DbSession,
    admin: AdminUser,
) -> dict:
    await _role_or_404(db, payload.role_id)
    if await db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    await db.execute(
        delete(UserHiddenRole).where(
            UserHiddenRole.season_id == season_id,
            UserHiddenRole.user_id == user_id,
        )
    )
    assignment = UserHiddenRole(
        season_id=season_id,
        user_id=user_id,
        role_id=payload.role_id,
        updated_by=admin.id,
    )
    db.add(assignment)
    await db.commit()
    await ws_events.broadcast_hidden_role_changed(season_id, user_id, "assigned")
    rows = await list_assignments(season_id, db, admin)
    return next(row for row in rows if row["user_id"] == user_id)


@router.delete("/seasons/{season_id}/users/{user_id}/hidden-role", status_code=204)
async def unassign_hidden_role(
    season_id: int, user_id: int, db: DbSession, admin: AdminUser
) -> None:
    await db.execute(
        delete(UserHiddenRole).where(
            UserHiddenRole.season_id == season_id,
            UserHiddenRole.user_id == user_id,
        )
    )
    await db.commit()
    await ws_events.broadcast_hidden_role_changed(season_id, user_id, "unassigned")


@router.get("/seasons/{season_id}/my-hidden-role", response_model=MyHiddenRoleRead)
async def my_hidden_role(
    season_id: int, db: DbSession, user: CurrentUser
) -> dict:
    result = await db.execute(
        select(
            UserHiddenRole.id,
            HiddenRole.id.label("role_id"),
            HiddenRole.name,
            HiddenRole.description,
            HiddenRole.success_condition,
            UserHiddenRole.is_revealed,
            UserHiddenRole.is_success,
        )
        .join(HiddenRole, HiddenRole.id == UserHiddenRole.role_id)
        .where(
            UserHiddenRole.season_id == season_id,
            UserHiddenRole.user_id == user.id,
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="배정된 히든롤이 없습니다.")
    return dict(row._mapping)
