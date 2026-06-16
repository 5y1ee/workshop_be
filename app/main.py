from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import (
    auth,
    gacha,
    game,
    game_round,
    game_session,
    result,
    reward,
    roulette,
    score,
    season,
    team,
    timetable,
    user,
)
from app.core.config import settings
from app.websocket import endpoint as ws_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    yield
    # shutdown


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # FE 도메인 정해지면 좁히기
        allow_credentials=False,  # JWT를 Authorization 헤더로 전송 → 쿠키 불필요. ["*"]와 호환됨
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST API
    app.include_router(auth.router, prefix="/api")
    app.include_router(season.router, prefix="/api")
    app.include_router(team.router, prefix="/api")
    app.include_router(user.router, prefix="/api")
    app.include_router(game.router, prefix="/api")
    app.include_router(timetable.router, prefix="/api")
    app.include_router(game_session.router, prefix="/api")
    app.include_router(game_round.router, prefix="/api")
    app.include_router(score.router, prefix="/api")
    app.include_router(result.router, prefix="/api")
    app.include_router(reward.router, prefix="/api")
    app.include_router(gacha.router, prefix="/api")
    app.include_router(roulette.router, prefix="/api")

    # WebSocket
    app.include_router(ws_endpoint.router)

    resources_dir = Path(__file__).resolve().parent.parent / "resources"
    app.mount("/resources", StaticFiles(directory=resources_dir), name="resources")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
