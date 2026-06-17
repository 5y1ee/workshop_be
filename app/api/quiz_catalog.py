from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, DbSession
from app.schemas.quiz_catalog import QuizCatalog, QuizSeedRequest, QuizSeedResult
from app.services import quiz_catalog_service
from app.services.quiz_catalog_service import QuizSeedError

router = APIRouter(tags=["quiz-catalog"])


@router.get("/quiz-catalog", response_model=QuizCatalog)
async def get_quiz_catalog(admin: AdminUser) -> dict:
    """퀴즈 대결 문제 카탈로그 (카테고리/문제 목록). 운영자 전용."""
    return quiz_catalog_service.get_catalog()


@router.post("/quiz-catalog/seed", response_model=QuizSeedResult)
async def seed_quiz_catalog(
    payload: QuizSeedRequest, db: DbSession, admin: AdminUser
) -> dict:
    """선택한 문제를 '퀴즈 대결' 세션에 대기 라운드로 적재. 운영자 전용."""
    try:
        return await quiz_catalog_service.seed_rounds(
            db,
            season_id=payload.season_id,
            admin_id=admin.id,
            categories=payload.categories,
            limit=payload.limit,
            shuffle=payload.shuffle,
            create_session=payload.create_session,
            replace=payload.replace,
            session_id=payload.session_id,
            game_title=payload.game_title,
        )
    except QuizSeedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
