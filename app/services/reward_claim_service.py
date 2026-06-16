"""리워드 수령(claim) 비즈니스 로직."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reward import Reward
from app.models.reward_claim import RewardClaim
from app.models.user import User
from app.schemas.reward_claim import RewardClaimDetail, RewardReadWithClaims


async def get_claim(
    db: AsyncSession, reward_id: int, user_id: int
) -> RewardClaim | None:
    result = await db.execute(
        select(RewardClaim).where(
            RewardClaim.reward_id == reward_id,
            RewardClaim.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def claim_reward(
    db: AsyncSession, reward: Reward, user_id: int, admin_id: int
) -> tuple[RewardClaim, bool]:
    """리워드를 수령 처리한다.

    Returns:
        (claim, created) — created=False 이면 이미 수령한 상태.
    """
    existing = await get_claim(db, reward.id, user_id)
    if existing:
        return existing, False

    claimed_count = await count_claims(db, reward.id)
    if claimed_count >= reward.total_count:
        raise ValueError("수령 가능한 수량을 초과했습니다.")

    claim = RewardClaim(
        reward_id=reward.id,
        user_id=user_id,
        created_by=admin_id,
    )
    db.add(claim)
    try:
        await db.commit()
        await db.refresh(claim)
    except IntegrityError:
        await db.rollback()
        existing = await get_claim(db, reward.id, user_id)
        return existing, False  # type: ignore[return-value]
    return claim, True


async def unclaim_reward(
    db: AsyncSession, reward_id: int, user_id: int
) -> bool:
    """수령 취소. 존재하지 않으면 False 반환."""
    claim = await get_claim(db, reward_id, user_id)
    if claim is None:
        return False
    await db.delete(claim)
    await db.commit()
    return True


async def count_claims(db: AsyncSession, reward_id: int) -> int:
    result = await db.execute(
        select(func.count()).where(RewardClaim.reward_id == reward_id)
    )
    return result.scalar_one()


async def list_claims(db: AsyncSession, reward_id: int) -> list[RewardClaimDetail]:
    """관리자용 — 수령자 목록 (닉네임 포함)."""
    rows = await db.execute(
        select(RewardClaim, User.nickname)
        .join(User, User.id == RewardClaim.user_id)
        .where(RewardClaim.reward_id == reward_id)
        .order_by(RewardClaim.claimed_at)
    )
    return [
        RewardClaimDetail(
            id=claim.id,
            reward_id=claim.reward_id,
            user_id=claim.user_id,
            nickname=nickname,
            claimed_at=claim.claimed_at,
        )
        for claim, nickname in rows
    ]


async def list_rewards_with_claims(
    db: AsyncSession, season_id: int, current_user_id: int
) -> list[RewardReadWithClaims]:
    """도감 목록 — 각 리워드에 수령 현황 + 본인 수령 여부 포함."""
    rewards_result = await db.execute(
        select(Reward).where(Reward.season_id == season_id).order_by(Reward.id)
    )
    rewards = list(rewards_result.scalars().all())

    if not rewards:
        return []

    reward_ids = [r.id for r in rewards]

    # 수령 건수 집계
    count_rows = await db.execute(
        select(RewardClaim.reward_id, func.count().label("cnt"))
        .where(RewardClaim.reward_id.in_(reward_ids))
        .group_by(RewardClaim.reward_id)
    )
    claim_counts: dict[int, int] = {row.reward_id: row.cnt for row in count_rows}

    # 본인 수령 여부
    my_rows = await db.execute(
        select(RewardClaim.reward_id).where(
            RewardClaim.reward_id.in_(reward_ids),
            RewardClaim.user_id == current_user_id,
        )
    )
    my_claimed_ids: set[int] = {row.reward_id for row in my_rows}

    return [
        RewardReadWithClaims(
            id=r.id,
            season_id=r.season_id,
            name=r.name,
            description=r.description,
            total_count=r.total_count,
            image_url=r.image_url,
            win_rate=r.win_rate,
            is_revealed=r.is_revealed,
            claimed_count=claim_counts.get(r.id, 0),
            remaining_count=r.total_count - claim_counts.get(r.id, 0),
            my_claimed=r.id in my_claimed_ids,
        )
        for r in rewards
    ]
