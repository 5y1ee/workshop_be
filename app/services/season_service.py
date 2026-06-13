"""시즌 비즈니스 로직."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.season import Season
from app.schemas.season import SeasonCreate, SeasonUpdate


def _utcnow() -> datetime:
    """TIMESTAMP (without time zone) 컬럼용 naive UTC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create_season(db: AsyncSession, data: SeasonCreate, admin_id: int) -> Season:
    season = Season(name=data.name, created_by=admin_id)
    db.add(season)
    await db.commit()
    await db.refresh(season)
    return season


async def list_seasons(db: AsyncSession) -> list[Season]:
    result = await db.execute(select(Season).order_by(Season.id))
    return list(result.scalars().all())


async def get_season(db: AsyncSession, season_id: int) -> Season | None:
    result = await db.execute(select(Season).where(Season.id == season_id))
    return result.scalar_one_or_none()


async def update_season(
    db: AsyncSession, season: Season, data: SeasonUpdate, admin_id: int
) -> Season:
    if data.name is not None:
        season.name = data.name

    if data.status is not None and data.status != season.status:
        # 상태 전이 시 시작/종료 시각 자동 기록
        if data.status == "active" and season.started_at is None:
            season.started_at = _utcnow()
        if data.status == "done" and season.ended_at is None:
            season.ended_at = _utcnow()
        season.status = data.status

    season.updated_by = admin_id
    season.updated_at = _utcnow()
    await db.commit()
    await db.refresh(season)
    return season
