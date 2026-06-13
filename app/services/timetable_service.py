"""타임테이블(시즌 진행표) 비즈니스 로직."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.timetable import Timetable
from app.schemas.timetable import TimetableCreate, TimetableUpdate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create_entry(
    db: AsyncSession, season_id: int, data: TimetableCreate
) -> Timetable:
    entry = Timetable(season_id=season_id, **data.model_dump())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_entries(db: AsyncSession, season_id: int) -> list[Timetable]:
    result = await db.execute(
        select(Timetable)
        .where(Timetable.season_id == season_id)
        .order_by(Timetable.order_index, Timetable.id)
    )
    return list(result.scalars().all())


async def get_entry(db: AsyncSession, entry_id: int) -> Timetable | None:
    result = await db.execute(select(Timetable).where(Timetable.id == entry_id))
    return result.scalar_one_or_none()


async def update_entry(
    db: AsyncSession, entry: Timetable, data: TimetableUpdate, admin_id: int
) -> Timetable:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    entry.updated_by = admin_id
    entry.updated_at = _utcnow()
    await db.commit()
    await db.refresh(entry)
    return entry
