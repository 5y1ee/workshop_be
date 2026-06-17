from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.reward import RewardCreate, RewardRead, RewardUpdate
from app.schemas.reward_claim import RewardClaimDetail, RewardReadWithClaims
from app.services import reward_claim_service, reward_service, season_service
from app.websocket import events as ws_events

router = APIRouter(tags=["rewards"])


async def _get_reward_or_404(db: DbSession, reward_id: int):
    reward = await reward_service.get_reward(db, reward_id)
    if reward is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="리워드를 찾을 수 없습니다."
        )
    return reward


async def _require_season(db: DbSession, season_id: int) -> None:
    if await season_service.get_season(db, season_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="시즌을 찾을 수 없습니다."
        )


@router.get("/seasons/{season_id}/rewards", response_model=list[RewardReadWithClaims])
async def list_rewards(
    season_id: int, db: DbSession, user: CurrentUser
) -> list[RewardReadWithClaims]:
    """시즌별 리워드 도감 — 수령 현황 + 본인 수령 여부 포함 (로그인 유저 누구나)."""
    return await reward_claim_service.list_rewards_with_claims(db, season_id, user.id)


@router.post(
    "/seasons/{season_id}/rewards",
    response_model=RewardRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_reward(
    season_id: int, payload: RewardCreate, db: DbSession, admin: AdminUser
) -> RewardRead:
    await _require_season(db, season_id)
    reward = await reward_service.create_reward(db, season_id, payload)
    await ws_events.broadcast_reward_catalog_changed(season_id, reward.id, "created")
    return reward


@router.patch("/rewards/{reward_id}", response_model=RewardRead)
async def update_reward(
    reward_id: int, payload: RewardUpdate, db: DbSession, admin: AdminUser
) -> RewardRead:
    reward = await _get_reward_or_404(db, reward_id)
    reward = await reward_service.update_reward(db, reward, payload, admin.id)
    await ws_events.broadcast_reward_catalog_changed(reward.season_id, reward.id, "updated")
    return reward


@router.delete("/rewards/{reward_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reward(reward_id: int, db: DbSession, admin: AdminUser) -> None:
    reward = await _get_reward_or_404(db, reward_id)
    season_id = reward.season_id
    await reward_service.delete_reward(db, reward)
    await ws_events.broadcast_reward_catalog_changed(season_id, reward_id, "deleted")


# --- claim ---


@router.post(
    "/rewards/{reward_id}/claim",
    response_model=RewardClaimDetail,
    status_code=status.HTTP_201_CREATED,
)
async def claim_reward(
    reward_id: int, db: DbSession, user: CurrentUser
) -> RewardClaimDetail:
    """본인이 직접 수령 처리 (도감에서 버튼 클릭)."""
    reward = await _get_reward_or_404(db, reward_id)
    try:
        claim, created = await reward_claim_service.claim_reward(
            db, reward, user_id=user.id, admin_id=user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    if not created:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 수령한 리워드입니다.",
        )

    claimed_count = await reward_claim_service.count_claims(db, reward_id)
    await ws_events.broadcast_reward_claimed(
        reward_id=reward.id,
        reward_name=reward.name,
        user_id=user.id,
        nickname=user.nickname,
        claimed_count=claimed_count,
        total_count=reward.total_count,
    )
    return RewardClaimDetail(
        id=claim.id,
        reward_id=claim.reward_id,
        user_id=claim.user_id,
        nickname=user.nickname,
        claimed_at=claim.claimed_at,
    )


@router.delete("/rewards/{reward_id}/claim", status_code=status.HTTP_204_NO_CONTENT)
async def unclaim_reward(reward_id: int, db: DbSession, user: CurrentUser) -> None:
    """수령 취소."""
    reward = await _get_reward_or_404(db, reward_id)
    deleted = await reward_claim_service.unclaim_reward(db, reward_id, user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="수령 내역이 없습니다.",
        )
    claimed_count = await reward_claim_service.count_claims(db, reward_id)
    await ws_events.broadcast_reward_unclaimed(
        reward_id=reward_id,
        claimed_count=claimed_count,
        total_count=reward.total_count,
    )


@router.get(
    "/rewards/{reward_id}/claims",
    response_model=list[RewardClaimDetail],
)
async def list_reward_claims(
    reward_id: int, db: DbSession, admin: AdminUser
) -> list[RewardClaimDetail]:
    """관리자용 — 수령자 목록 조회."""
    await _get_reward_or_404(db, reward_id)
    return await reward_claim_service.list_claims(db, reward_id)
