from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import AdminUser, DbSession
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


async def _get_or_404(db: DbSession, user_id: int):
    user = await user_service.get_user(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="유저를 찾을 수 없습니다."
        )
    return user


async def _validate_team(db: DbSession, team_id: int | None) -> None:
    if team_id is not None and not await user_service.team_exists(db, team_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="존재하지 않는 팀입니다.",
        )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate, db: DbSession, admin: AdminUser
) -> UserRead:
    if await user_service.get_user_by_username(db, payload.username) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 아이디입니다.",
        )
    await _validate_team(db, payload.team_id)
    return await user_service.create_user(db, payload)


@router.get("", response_model=list[UserRead])
async def list_users(
    db: DbSession,
    admin: AdminUser,
    role: Annotated[str | None, Query()] = None,
    team_id: Annotated[int | None, Query()] = None,
) -> list[UserRead]:
    return await user_service.list_users(db, role=role, team_id=team_id)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: int, db: DbSession, admin: AdminUser) -> UserRead:
    return await _get_or_404(db, user_id)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int, payload: UserUpdate, db: DbSession, admin: AdminUser
) -> UserRead:
    user = await _get_or_404(db, user_id)
    if "team_id" in payload.model_fields_set:
        await _validate_team(db, payload.team_id)
    return await user_service.update_user(db, user, payload, admin.id)
