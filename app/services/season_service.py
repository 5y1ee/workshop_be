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
    """삭제되지 않은 시즌만."""
    result = await db.execute(
        select(Season).where(Season.del_yn.is_(False)).order_by(Season.id)
    )
    return list(result.scalars().all())


async def get_season(db: AsyncSession, season_id: int) -> Season | None:
    result = await db.execute(
        select(Season).where(Season.id == season_id, Season.del_yn.is_(False))
    )
    return result.scalar_one_or_none()


async def get_active_season(db: AsyncSession) -> Season | None:
    """현재 활성(active) 시즌 (여러 개면 가장 최근)."""
    result = await db.execute(
        select(Season)
        .where(Season.status == "active", Season.del_yn.is_(False))
        .order_by(Season.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def delete_season(db: AsyncSession, season: Season, admin_id: int) -> None:
    """소프트 삭제."""
    season.del_yn = True
    season.updated_by = admin_id
    season.updated_at = _utcnow()
    await db.commit()


async def update_season(
    db: AsyncSession, season: Season, data: SeasonUpdate, admin_id: int
) -> Season:
    if data.name is not None:
        season.name = data.name
    if data.gacha_pull_cost is not None:
        season.gacha_pull_cost = data.gacha_pull_cost

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
