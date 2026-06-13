from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.game import GameCreate, GameRead, GameUpdate
from app.services import game_service

router = APIRouter(prefix="/games", tags=["games"])


async def _get_or_404(db: DbSession, game_id: int):
    game = await game_service.get_game(db, game_id)
    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="게임을 찾을 수 없습니다."
        )
    return game


@router.post("", response_model=GameRead, status_code=status.HTTP_201_CREATED)
async def create_game(payload: GameCreate, db: DbSession, admin: AdminUser) -> GameRead:
    return await game_service.create_game(db, payload)


@router.get("", response_model=list[GameRead])
async def list_games(db: DbSession, user: CurrentUser) -> list[GameRead]:
    return await game_service.list_games(db)


@router.get("/{game_id}", response_model=GameRead)
async def get_game(game_id: int, db: DbSession, user: CurrentUser) -> GameRead:
    return await _get_or_404(db, game_id)


@router.patch("/{game_id}", response_model=GameRead)
async def update_game(
    game_id: int, payload: GameUpdate, db: DbSession, admin: AdminUser
) -> GameRead:
    game = await _get_or_404(db, game_id)
    return await game_service.update_game(db, game, payload, admin.id)
