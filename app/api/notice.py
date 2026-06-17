from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.models.notice import Notice
from app.schemas.notice import CurrentNoticeRead, NoticeCreate, NoticeRead
from app.services import notice_service, season_service
from app.websocket.events import broadcast_notice_created, broadcast_notice_deleted

router = APIRouter(tags=["notices"])


async def _require_season(db: DbSession, season_id: int) -> None:
    if await season_service.get_season(db, season_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="시즌을 찾을 수 없습니다.",
        )


async def _get_notice_or_404(db: DbSession, notice_id: int) -> Notice:
    notice = await notice_service.get_notice(db, notice_id)
    if notice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공지를 찾을 수 없습니다.",
        )
    return notice


@router.get(
    "/seasons/{season_id}/notices/current",
    response_model=CurrentNoticeRead,
)
async def current_notice(
    season_id: int, db: DbSession, user: CurrentUser
) -> CurrentNoticeRead:
    await _require_season(db, season_id)
    notice = await notice_service.current_notice(db, season_id)
    return CurrentNoticeRead(
        notice=NoticeRead.model_validate(notice) if notice is not None else None
    )


@router.get("/seasons/{season_id}/notices", response_model=list[NoticeRead])
async def list_notices(
    season_id: int, db: DbSession, admin: AdminUser
) -> list[Notice]:
    await _require_season(db, season_id)
    return await notice_service.list_notices(db, season_id)


@router.post(
    "/seasons/{season_id}/notices",
    response_model=NoticeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_notice(
    season_id: int,
    payload: NoticeCreate,
    db: DbSession,
    admin: AdminUser,
) -> Notice:
    await _require_season(db, season_id)
    if not payload.message.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="공지 내용을 입력하세요.",
        )
    notice = await notice_service.create_notice(db, season_id, payload, admin.id)
    await broadcast_notice_created(notice)
    return notice


@router.delete("/notices/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notice(notice_id: int, db: DbSession, admin: AdminUser) -> None:
    notice = await _get_notice_or_404(db, notice_id)
    notice = await notice_service.delete_notice(db, notice)
    await broadcast_notice_deleted(notice.season_id, notice.id)
