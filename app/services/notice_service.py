"""시즌별 실시간 공지 비즈니스 로직."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notice import Notice
from app.schemas.notice import NoticeCreate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def current_notice(db: AsyncSession, season_id: int) -> Notice | None:
    now = _utcnow()
    result = await db.execute(
        select(Notice)
        .where(
            Notice.season_id == season_id,
            Notice.deleted_at.is_(None),
            Notice.expires_at > now,
        )
        .order_by(Notice.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_notices(db: AsyncSession, season_id: int) -> list[Notice]:
    result = await db.execute(
        select(Notice)
        .where(Notice.season_id == season_id, Notice.deleted_at.is_(None))
        .order_by(Notice.created_at.desc(), Notice.id.desc())
        .limit(30)
    )
    return list(result.scalars().all())


async def create_notice(
    db: AsyncSession, season_id: int, data: NoticeCreate, admin_id: int
) -> Notice:
    now = _utcnow()
    active_result = await db.execute(
        select(Notice).where(
            Notice.season_id == season_id,
            Notice.deleted_at.is_(None),
            Notice.expires_at > now,
        )
    )
    for active in active_result.scalars().all():
        active.deleted_at = now

    notice = Notice(
        season_id=season_id,
        message=data.message.strip(),
        expires_at=now + timedelta(minutes=data.duration_minutes),
        created_by=admin_id,
    )
    db.add(notice)
    await db.commit()
    await db.refresh(notice)
    return notice


async def get_notice(db: AsyncSession, notice_id: int) -> Notice | None:
    result = await db.execute(select(Notice).where(Notice.id == notice_id))
    return result.scalar_one_or_none()


async def delete_notice(db: AsyncSession, notice: Notice) -> Notice:
    notice.deleted_at = _utcnow()
    await db.commit()
    await db.refresh(notice)
    return notice
