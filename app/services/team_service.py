"""팀 비즈니스 로직."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.models.user import User
from app.schemas.team import TeamCreate, TeamUpdate


async def create_team(db: AsyncSession, season_id: int, data: TeamCreate) -> Team:
    team = Team(season_id=season_id, name=data.name)
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return team


async def list_teams(db: AsyncSession, season_id: int) -> list[Team]:
    result = await db.execute(
        select(Team).where(Team.season_id == season_id).order_by(Team.id)
    )
    return list(result.scalars().all())


async def get_team(db: AsyncSession, team_id: int) -> Team | None:
    result = await db.execute(select(Team).where(Team.id == team_id))
    return result.scalar_one_or_none()


async def update_team(db: AsyncSession, team: Team, data: TeamUpdate) -> Team:
    team.name = data.name
    await db.commit()
    await db.refresh(team)
    return team


async def list_members(db: AsyncSession, team_id: int) -> list[User]:
    """팀 소속 유저 목록 (포인트 내림차순)."""
    result = await db.execute(
        select(User)
        .where(User.team_id == team_id)
        .order_by(User.point.desc(), User.id)
    )
    return list(result.scalars().all())
