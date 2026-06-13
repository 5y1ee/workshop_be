from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, game, season, team, timetable, user
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
        allow_credentials=True,
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

    # WebSocket
    app.include_router(ws_endpoint.router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
