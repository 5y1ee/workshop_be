from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.team import TeamCreate, TeamRead, TeamUpdate
from app.services import season_service, team_service

router = APIRouter(tags=["teams"])


async def _get_team_or_404(db: DbSession, team_id: int):
    team = await team_service.get_team(db, team_id)
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="팀을 찾을 수 없습니다."
        )
    return team


@router.post(
    "/seasons/{season_id}/teams",
    response_model=TeamRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_team(
    season_id: int, payload: TeamCreate, db: DbSession, admin: AdminUser
) -> TeamRead:
    if await season_service.get_season(db, season_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="시즌을 찾을 수 없습니다."
        )
    return await team_service.create_team(db, season_id, payload)


@router.get("/seasons/{season_id}/teams", response_model=list[TeamRead])
async def list_teams(
    season_id: int, db: DbSession, user: CurrentUser
) -> list[TeamRead]:
    return await team_service.list_teams(db, season_id)


@router.get("/teams/{team_id}", response_model=TeamRead)
async def get_team(team_id: int, db: DbSession, user: CurrentUser) -> TeamRead:
    return await _get_team_or_404(db, team_id)


@router.patch("/teams/{team_id}", response_model=TeamRead)
async def update_team(
    team_id: int, payload: TeamUpdate, db: DbSession, admin: AdminUser
) -> TeamRead:
    team = await _get_team_or_404(db, team_id)
    return await team_service.update_team(db, team, payload)
