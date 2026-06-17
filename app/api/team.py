from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.team import (
    MemberAssign,
    MyTeam,
    SeasonMembership,
    TeamCreate,
    TeamMember,
    TeamRead,
    TeamUpdate,
)
from app.services import season_service, team_service, user_service
from app.websocket.events import broadcast_team_membership_changed

router = APIRouter(tags=["teams"])


async def _get_team_or_404(db: DbSession, team_id: int):
    team = await team_service.get_team(db, team_id)
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="팀을 찾을 수 없습니다."
        )
    return team


async def _require_season(db: DbSession, season_id: int) -> None:
    if await season_service.get_season(db, season_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="시즌을 찾을 수 없습니다."
        )


@router.post(
    "/seasons/{season_id}/teams",
    response_model=TeamRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_team(
    season_id: int, payload: TeamCreate, db: DbSession, admin: AdminUser
) -> TeamRead:
    await _require_season(db, season_id)
    return await team_service.create_team(db, season_id, payload)


@router.get("/seasons/{season_id}/teams", response_model=list[TeamRead])
async def list_teams(
    season_id: int, db: DbSession, user: CurrentUser
) -> list[TeamRead]:
    return await team_service.list_teams(db, season_id)


@router.get("/teams/{team_id}", response_model=TeamRead)
async def get_team(team_id: int, db: DbSession, user: CurrentUser) -> TeamRead:
    return await _get_team_or_404(db, team_id)


@router.get("/teams/{team_id}/members", response_model=list[TeamMember])
async def list_team_members(
    team_id: int, db: DbSession, user: CurrentUser
) -> list[TeamMember]:
    """팀 소속 멤버 목록 (로그인 유저 누구나 조회 가능, 포인트 내림차순)."""
    await _get_team_or_404(db, team_id)
    return await team_service.list_members(db, team_id)


@router.patch("/teams/{team_id}", response_model=TeamRead)
async def update_team(
    team_id: int, payload: TeamUpdate, db: DbSession, admin: AdminUser
) -> TeamRead:
    team = await _get_team_or_404(db, team_id)
    return await team_service.update_team(db, team, payload)


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(team_id: int, db: DbSession, admin: AdminUser) -> None:
    """팀 소프트 삭제 (멤버 배정은 해제됨)."""
    team = await _get_team_or_404(db, team_id)
    await team_service.delete_team(db, team)


# ---------- 시즌별 멤버십 (유저 배치) ----------

@router.get("/seasons/{season_id}/members", response_model=list[SeasonMembership])
async def list_season_members(
    season_id: int, db: DbSession, user: CurrentUser
) -> list[SeasonMembership]:
    """시즌 내 유저-팀 배정 현황."""
    rows = await team_service.list_season_memberships(db, season_id)
    return [SeasonMembership(user_id=r.user_id, team_id=r.team_id) for r in rows]


@router.post(
    "/seasons/{season_id}/teams/{team_id}/members",
    response_model=SeasonMembership,
    status_code=status.HTTP_201_CREATED,
)
async def assign_member(
    season_id: int,
    team_id: int,
    payload: MemberAssign,
    db: DbSession,
    admin: AdminUser,
) -> SeasonMembership:
    """유저를 시즌의 팀에 배정 (같은 시즌 기존 배정은 교체)."""
    await _require_season(db, season_id)
    team = await _get_team_or_404(db, team_id)
    if team.season_id != season_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="팀이 해당 시즌 소속이 아닙니다.",
        )
    if await user_service.get_user(db, payload.user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="유저를 찾을 수 없습니다."
        )
    m = await team_service.assign_member(db, season_id, team_id, payload.user_id)
    await broadcast_team_membership_changed(season_id, m.user_id, m.team_id, "assigned")
    return SeasonMembership(user_id=m.user_id, team_id=m.team_id)


@router.delete(
    "/seasons/{season_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unassign_member(
    season_id: int, user_id: int, db: DbSession, admin: AdminUser
) -> None:
    await team_service.unassign_member(db, season_id, user_id)
    await broadcast_team_membership_changed(season_id, user_id, None, "unassigned")


@router.get("/seasons/{season_id}/my-team", response_model=MyTeam)
async def my_team(
    season_id: int, db: DbSession, user: CurrentUser
) -> MyTeam:
    """선택 시즌에서 내 소속 팀 (없으면 null)."""
    team = await team_service.get_my_team(db, season_id, user.id)
    if team is None:
        return MyTeam(team_id=None, name=None)
    return MyTeam(team_id=team.id, name=team.name)
