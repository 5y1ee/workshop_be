"""가챠(뽑기) 비즈니스 로직.

흐름:
  1. 유저 포인트 1 차감 (부족하면 ValueError)
  2. 잔여 수량이 있는 리워드 목록 로드
  3. win_rate 합산으로 당첨/꽝 판정
  4. 당첨이면 win_rate 비례 랜덤으로 리워드 선택
  5. reward_claim 생성 + is_revealed = true
  6. (reward, is_win, remaining_point) 반환
"""

import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reward import Reward
from app.models.reward_claim import RewardClaim
from app.models.user import User


async def _remaining_count(db: AsyncSession, reward_id: int) -> int:
    result = await db.execute(
        select(func.count()).where(RewardClaim.reward_id == reward_id)
    )
    return result.scalar_one()


async def pull(
    db: AsyncSession, user: User, season_id: int
) -> tuple[Reward | None, bool, int]:
    """뽑기 1회 실행.

    Returns:
        (reward, is_win, remaining_point)
        is_win=False 이면 reward=None (꽝)
    """
    if user.point < 1:
        raise ValueError("포인트가 부족합니다.")

    # 포인트 차감
    user.point -= 1
    await db.flush()

    # 잔여 수량 있는 리워드 목록
    reward_rows = await db.execute(
        select(Reward).where(
            Reward.season_id == season_id,
            Reward.win_rate > 0,
        )
    )
    all_rewards = list(reward_rows.scalars().all())

    # 본인이 이미 받은 리워드 ID 조회
    my_claims_result = await db.execute(
        select(RewardClaim.reward_id).where(
            RewardClaim.reward_id.in_([r.id for r in all_rewards]),
            RewardClaim.user_id == user.id,
        )
    )
    my_claimed_ids: set[int] = {row.reward_id for row in my_claims_result}

    # 잔여 수량 있고 본인이 아직 안 받은 리워드만
    available: list[Reward] = []
    for r in all_rewards:
        if r.id in my_claimed_ids:
            continue
        claimed = await _remaining_count(db, r.id)
        if claimed < r.total_count:
            available.append(r)

    if not available:
        # 뽑을 수 있는 리워드 없음 → 꽝 처리 (포인트는 차감)
        await db.commit()
        await db.refresh(user)
        return None, False, user.point

    total_win_rate = sum(r.win_rate for r in available)
    rand = random.random()

    if rand > total_win_rate:
        # 꽝
        await db.commit()
        await db.refresh(user)
        return None, False, user.point

    # 당첨 — win_rate 비례로 리워드 선택
    pick = random.uniform(0, total_win_rate)
    cumulative = 0.0
    selected: Reward = available[0]
    for r in available:
        cumulative += r.win_rate
        if pick <= cumulative:
            selected = r
            break

    # claim 생성
    claim = RewardClaim(
        reward_id=selected.id,
        user_id=user.id,
        created_by=user.id,
    )
    db.add(claim)

    # 최초 당첨이면 is_revealed = true
    if not selected.is_revealed:
        selected.is_revealed = True

    await db.commit()
    await db.refresh(user)
    await db.refresh(selected)
    return selected, True, user.point
