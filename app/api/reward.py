from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.reward import RewardRead
from app.services import reward_service

router = APIRouter(prefix="/rewards", tags=["rewards"])


@router.get("", response_model=list[RewardRead])
async def list_rewards(db: DbSession, user: CurrentUser) -> list[RewardRead]:
    """리워드 도감 목록 (로그인 유저 누구나 조회 가능)."""
    return await reward_service.list_rewards(db)


@router.get("/{reward_id}", response_model=RewardRead)
async def get_reward(reward_id: int, db: DbSession, user: CurrentUser) -> RewardRead:
    reward = await reward_service.get_reward(db, reward_id)
    if reward is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="리워드를 찾을 수 없습니다."
        )
    return reward
