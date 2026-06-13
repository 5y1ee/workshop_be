"""유저 비즈니스 로직."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.team import Team
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def get_user(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def list_users(
    db: AsyncSession,
    role: str | None = None,
    team_id: int | None = None,
) -> list[User]:
    stmt = select(User).order_by(User.id)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if team_id is not None:
        stmt = stmt.where(User.team_id == team_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def team_exists(db: AsyncSession, team_id: int) -> bool:
    result = await db.execute(select(Team.id).where(Team.id == team_id))
    return result.scalar_one_or_none() is not None


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    user = User(
        username=data.username,
        password=hash_password(data.password),
        nickname=data.nickname,
        role=data.role,
        team_id=data.team_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession, user: User, data: UserUpdate, admin_id: int
) -> User:
    fields = data.model_dump(exclude_unset=True)
    if "password" in fields:
        user.password = hash_password(fields.pop("password"))
    for key, value in fields.items():
        setattr(user, key, value)
    user.updated_by = admin_id
    user.updated_at = _utcnow()
    await db.commit()
    await db.refresh(user)
    return user
