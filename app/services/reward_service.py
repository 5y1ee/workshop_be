"""리워드(시즌별 도감) 비즈니스 로직."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reward import Reward
from app.schemas.reward import RewardCreate, RewardUpdate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def list_rewards(db: AsyncSession, season_id: int) -> list[Reward]:
    result = await db.execute(
        select(Reward).where(Reward.season_id == season_id).order_by(Reward.id)
    )
    return list(result.scalars().all())


async def get_reward(db: AsyncSession, reward_id: int) -> Reward | None:
    result = await db.execute(select(Reward).where(Reward.id == reward_id))
    return result.scalar_one_or_none()


async def create_reward(
    db: AsyncSession, season_id: int, data: RewardCreate
) -> Reward:
    reward = Reward(
        season_id=season_id,
        name=data.name,
        description=data.description,
        total_count=data.total_count,
        image_url=data.image_url,
        win_rate=round(data.win_rate_pct / 100, 4),
    )
    db.add(reward)
    await db.commit()
    await db.refresh(reward)
    return reward


async def update_reward(
    db: AsyncSession, reward: Reward, data: RewardUpdate, admin_id: int
) -> Reward:
    fields = data.model_dump(exclude_unset=True)
    if "win_rate_pct" in fields:
        reward.win_rate = round(fields.pop("win_rate_pct") / 100, 4)
    for key, value in fields.items():
        setattr(reward, key, value)
    reward.updated_by = admin_id
    reward.updated_at = _utcnow()
    await db.commit()
    await db.refresh(reward)
    return reward


async def delete_reward(db: AsyncSession, reward: Reward) -> None:
    await db.delete(reward)
    await db.commit()
