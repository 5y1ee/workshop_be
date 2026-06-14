"""리워드(도감) 비즈니스 로직."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reward import Reward


async def list_rewards(db: AsyncSession) -> list[Reward]:
    result = await db.execute(select(Reward).order_by(Reward.id))
    return list(result.scalars().all())


async def get_reward(db: AsyncSession, reward_id: int) -> Reward | None:
    result = await db.execute(select(Reward).where(Reward.id == reward_id))
    return result.scalar_one_or_none()
