from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import and_, select

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.models.buff import Buff, TeamBuff
from app.models.game_session import GameSession
from app.models.team import Team
from app.models.team_member import TeamMembership
from app.models.timetable import Timetable
from app.schemas.buff import BuffCreate, BuffRead, BuffUpdate, TeamBuffCreate, TeamBuffRead
from app.websocket import events as ws_events

router = APIRouter(tags=["buffs"])


ACTIVE_STATES = {"ready", "in_progress", "scoring", "reward"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _buff_or_404(db: DbSession, buff_id: int) -> Buff:
    buff = await db.get(Buff, buff_id)
    if buff is None:
        raise HTTPException(status_code=404, detail="버프/디버프를 찾을 수 없습니다.")
    return buff


async def _team_buff_rows(db: DbSession, *, season_id: int | None = None, session_id: int | None = None, team_id: int | None = None) -> list[dict]:
    stmt = (
        select(
            TeamBuff.id,
            TeamBuff.team_id,
            Team.name.label("team_name"),
            Buff.id.label("buff_id"),
            Buff.name.label("buff_name"),
            Buff.description.label("buff_description"),
            Buff.type.label("buff_type"),
            Buff.effect_type,
            Buff.duration,
            TeamBuff.session_id,
            GameSession.state.label("session_state"),
            TeamBuff.is_active,
            TeamBuff.activated_at,
        )
        .join(Team, Team.id == TeamBuff.team_id)
        .join(Buff, Buff.id == TeamBuff.buff_id)
        .join(GameSession, GameSession.id == TeamBuff.session_id)
        .order_by(TeamBuff.id)
    )
    if season_id is not None:
        stmt = stmt.where(Team.season_id == season_id)
    if session_id is not None:
        stmt = stmt.where(TeamBuff.session_id == session_id)
    if team_id is not None:
        stmt = stmt.where(TeamBuff.team_id == team_id)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


@router.get("/buffs", response_model=list[BuffRead])
async def list_buffs(db: DbSession, user: CurrentUser) -> list[Buff]:
    result = await db.execute(select(Buff).order_by(Buff.id))
    return list(result.scalars().all())


@router.post("/buffs", response_model=BuffRead, status_code=201)
async def create_buff(payload: BuffCreate, db: DbSession, admin: AdminUser) -> Buff:
    buff = Buff(**payload.model_dump(), updated_by=admin.id)
    db.add(buff)
    await db.commit()
    await db.refresh(buff)
    await ws_events.broadcast_team_buff_changed(None, None, "catalog_changed")
    return buff


@router.patch("/buffs/{buff_id}", response_model=BuffRead)
async def update_buff(
    buff_id: int, payload: BuffUpdate, db: DbSession, admin: AdminUser
) -> Buff:
    buff = await _buff_or_404(db, buff_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(buff, key, value)
    buff.updated_by = admin.id
    buff.updated_at = _utcnow()
    await db.commit()
    await db.refresh(buff)
    await ws_events.broadcast_team_buff_changed(None, None, "catalog_changed")
    return buff


@router.delete("/buffs/{buff_id}", status_code=204)
async def delete_buff(buff_id: int, db: DbSession, admin: AdminUser) -> None:
    buff = await _buff_or_404(db, buff_id)
    from sqlalchemy import delete

    await db.execute(delete(TeamBuff).where(TeamBuff.buff_id == buff_id))
    await db.delete(buff)
    await db.commit()
    await ws_events.broadcast_team_buff_changed(None, None, "catalog_changed")


@router.get("/seasons/{season_id}/team-buffs", response_model=list[TeamBuffRead])
async def list_team_buffs(season_id: int, db: DbSession, admin: AdminUser) -> list[dict]:
    return await _team_buff_rows(db, season_id=season_id)


@router.post("/sessions/{session_id}/team-buffs", response_model=TeamBuffRead, status_code=201)
async def assign_team_buff(
    session_id: int, payload: TeamBuffCreate, db: DbSession, admin: AdminUser
) -> dict:
    session = await db.get(GameSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="게임 세션을 찾을 수 없습니다.")
    if await db.get(Team, payload.team_id) is None:
        raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다.")
    await _buff_or_404(db, payload.buff_id)
    item = TeamBuff(
        team_id=payload.team_id,
        buff_id=payload.buff_id,
        session_id=session_id,
        activated_at=_utcnow() if session.state in ACTIVE_STATES else None,
        created_by=admin.id,
    )
    db.add(item)
    await db.commit()
    await ws_events.broadcast_team_buff_changed(session_id, payload.team_id, "assigned")
    return (await _team_buff_rows(db, session_id=session_id, team_id=payload.team_id))[-1]


@router.delete("/team-buffs/{team_buff_id}", status_code=204)
async def delete_team_buff(team_buff_id: int, db: DbSession, admin: AdminUser) -> None:
    item = await db.get(TeamBuff, team_buff_id)
    if item is None:
        raise HTTPException(status_code=404, detail="팀 버프를 찾을 수 없습니다.")
    session_id = item.session_id
    team_id = item.team_id
    await db.delete(item)
    await db.commit()
    await ws_events.broadcast_team_buff_changed(session_id, team_id, "deleted")


@router.get("/sessions/{session_id}/my-team-buffs", response_model=list[TeamBuffRead])
async def my_team_buffs(session_id: int, db: DbSession, user: CurrentUser) -> list[dict]:
    session = await db.get(GameSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="게임 세션을 찾을 수 없습니다.")
    membership = await db.scalar(
        select(TeamMembership)
        .join(GameSession, GameSession.id == session_id)
        .join(Timetable, Timetable.id == GameSession.timetable_id)
        .where(
            TeamMembership.user_id == user.id,
            TeamMembership.season_id == Timetable.season_id,
        )
    )
    if membership is None or session.state not in ACTIVE_STATES:
        return []
    rows = await _team_buff_rows(db, session_id=session_id, team_id=membership.team_id)
    return [row for row in rows if row["is_active"]]
