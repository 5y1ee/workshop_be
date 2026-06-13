from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.season import SeasonCreate, SeasonRead, SeasonUpdate
from app.services import season_service

router = APIRouter(prefix="/seasons", tags=["seasons"])


async def _get_or_404(db: DbSession, season_id: int):
    season = await season_service.get_season(db, season_id)
    if season is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="시즌을 찾을 수 없습니다."
        )
    return season


@router.post("", response_model=SeasonRead, status_code=status.HTTP_201_CREATED)
async def create_season(
    payload: SeasonCreate, db: DbSession, admin: AdminUser
) -> SeasonRead:
    return await season_service.create_season(db, payload, admin.id)


@router.get("", response_model=list[SeasonRead])
async def list_seasons(db: DbSession, user: CurrentUser) -> list[SeasonRead]:
    return await season_service.list_seasons(db)


@router.get("/{season_id}", response_model=SeasonRead)
async def get_season(season_id: int, db: DbSession, user: CurrentUser) -> SeasonRead:
    return await _get_or_404(db, season_id)


@router.patch("/{season_id}", response_model=SeasonRead)
async def update_season(
    season_id: int, payload: SeasonUpdate, db: DbSession, admin: AdminUser
) -> SeasonRead:
    season = await _get_or_404(db, season_id)
    return await season_service.update_season(db, season, payload, admin.id)
