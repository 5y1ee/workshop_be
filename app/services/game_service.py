"""게임(정의) 비즈니스 로직."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game
from app.schemas.game import GameCreate, GameUpdate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create_game(db: AsyncSession, data: GameCreate) -> Game:
    game = Game(**data.model_dump())
    db.add(game)
    await db.commit()
    await db.refresh(game)
    return game


async def list_games(db: AsyncSession) -> list[Game]:
    result = await db.execute(select(Game).order_by(Game.id))
    return list(result.scalars().all())


async def get_game(db: AsyncSession, game_id: int) -> Game | None:
    result = await db.execute(select(Game).where(Game.id == game_id))
    return result.scalar_one_or_none()


async def game_exists(db: AsyncSession, game_id: int) -> bool:
    result = await db.execute(select(Game.id).where(Game.id == game_id))
    return result.scalar_one_or_none() is not None


async def update_game(
    db: AsyncSession, game: Game, data: GameUpdate, admin_id: int
) -> Game:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(game, key, value)
    game.updated_by = admin_id
    game.updated_at = _utcnow()
    await db.commit()
    await db.refresh(game)
    return game
