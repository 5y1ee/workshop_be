from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession
from app.schemas.notice import NoticeCreate
from app.schemas.reward import RewardRead
from app.services import gacha_service, notice_service
from app.services.reward_claim_service import count_claims
from app.websocket import events as ws_events

router = APIRouter(tags=["gacha"])


class GachaPullResponse(BaseModel):
    is_win: bool
    reward: RewardRead | None = None
    remaining_point: int
    pull_cost: int


@router.post("/gacha/pull", response_model=GachaPullResponse)
async def pull_gacha(
    season_id: int,
    db: DbSession,
    user: CurrentUser,
) -> GachaPullResponse:
    """가챠 뽑기 1회 (포인트 1 소모).

    - is_win=true: reward 필드에 당첨 리워드 반환
    - is_win=false: 꽝 (reward=null)
    """
    try:
        reward, is_win, remaining_point, pull_cost = await gacha_service.pull(
            db, user, season_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(e))

    if is_win and reward is not None:
        claimed_count = await count_claims(db, reward.id)
        await ws_events.broadcast_reward_claimed(
            reward_id=reward.id,
            reward_name=reward.name,
            user_id=user.id,
            nickname=user.nickname,
            claimed_count=claimed_count,
            total_count=reward.total_count,
        )

        # 당첨 사실을 1분짜리 공지로 자동 등록 (기존 공지 시스템 재사용)
        notice = await notice_service.create_notice(
            db,
            season_id,
            NoticeCreate(
                message=f"🎰 {user.nickname} 님이 '{reward.name}' 을(를) 뽑았어요!",
                duration_minutes=1,
            ),
            admin_id=user.id,
        )
        await ws_events.broadcast_notice_created(notice)

    return GachaPullResponse(
        is_win=is_win,
        reward=RewardRead.model_validate(reward) if reward else None,
        remaining_point=remaining_point,
        pull_cost=pull_cost,
    )
