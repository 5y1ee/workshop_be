from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.timetable import TimetableCreate, TimetableRead, TimetableUpdate
from app.services import game_service, season_service, timetable_service

router = APIRouter(tags=["timetable"])


async def _get_entry_or_404(db: DbSession, entry_id: int):
    entry = await timetable_service.get_entry(db, entry_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="타임테이블 항목을 찾을 수 없습니다.",
        )
    return entry


async def _validate_game(db: DbSession, game_id: int) -> None:
    if not await game_service.game_exists(db, game_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="존재하지 않는 게임입니다."
        )


@router.post(
    "/seasons/{season_id}/timetable",
    response_model=TimetableRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_timetable_entry(
    season_id: int, payload: TimetableCreate, db: DbSession, admin: AdminUser
) -> TimetableRead:
    if await season_service.get_season(db, season_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="시즌을 찾을 수 없습니다."
        )
    await _validate_game(db, payload.game_id)
    return await timetable_service.create_entry(db, season_id, payload)


@router.get("/seasons/{season_id}/timetable", response_model=list[TimetableRead])
async def list_timetable(
    season_id: int, db: DbSession, user: CurrentUser
) -> list[TimetableRead]:
    return await timetable_service.list_entries(db, season_id)


@router.get("/timetable/{entry_id}", response_model=TimetableRead)
async def get_timetable_entry(
    entry_id: int, db: DbSession, user: CurrentUser
) -> TimetableRead:
    return await _get_entry_or_404(db, entry_id)


@router.patch("/timetable/{entry_id}", response_model=TimetableRead)
async def update_timetable_entry(
    entry_id: int, payload: TimetableUpdate, db: DbSession, admin: AdminUser
) -> TimetableRead:
    entry = await _get_entry_or_404(db, entry_id)
    if payload.game_id is not None:
        await _validate_game(db, payload.game_id)
    return await timetable_service.update_entry(db, entry, payload, admin.id)
