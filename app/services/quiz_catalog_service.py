"""퀴즈 대결 문제 카탈로그 조회 + 세션 적재 비즈니스 로직.

`scripts.quiz_data` 의 객관식 문제를 운영 관리 페이지(문제 데이터 탭)에서
조회하고, '퀴즈 대결' 세션에 GameRound(button 타입)로 적재한다.
CLI 스크립트 `scripts.seed_quiz` 와 동일한 동작을 API 로 노출한다.
"""

from __future__ import annotations

import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game
from app.models.game_round import GameRound, RoundSubmission
from app.models.game_session import GameSession
from app.models.timetable import Timetable
from scripts.quiz_data import (
    QUIZ_QUESTIONS,
    QuizQuestion,
    category_counts,
    validate,
)

DEFAULT_GAME_TITLE = "퀴즈 대결"


class QuizSeedError(Exception):
    """문제 적재 중 발생한 사용자 표시용 오류."""


def get_catalog() -> dict:
    """전체 문제 카탈로그 (카테고리/문제 수 + 문제 목록)."""
    counts = category_counts()
    return {
        "total": len(QUIZ_QUESTIONS),
        "categories": [{"name": name, "count": cnt} for name, cnt in counts.items()],
        "questions": [
            {
                "category": q.category,
                "prompt": q.prompt,
                "options": list(q.options),
                "answer": q.answer,
            }
            for q in QUIZ_QUESTIONS
        ],
    }


def _select_questions(
    categories: list[str] | None, limit: int | None, shuffle: bool
) -> list[QuizQuestion]:
    items = list(QUIZ_QUESTIONS)
    if categories:
        wanted = set(categories)
        items = [q for q in items if q.category in wanted]
    if shuffle:
        random.shuffle(items)
    if limit is not None:
        items = items[:limit]
    return items


async def _resolve_session(
    db: AsyncSession,
    *,
    season_id: int,
    game_title: str,
    session_id: int | None,
    create_session: bool,
    admin_id: int | None,
) -> GameSession:
    """대상 세션 결정. seed_quiz._find_session 과 동일한 규칙."""
    if session_id is not None:
        session = await db.get(GameSession, session_id)
        if session is None:
            raise QuizSeedError(f"session_id={session_id} 세션을 찾을 수 없습니다.")
        return session

    game = await db.scalar(select(Game).where(Game.title == game_title))
    if game is None:
        raise QuizSeedError(f"'{game_title}' 게임을 찾을 수 없습니다.")

    timetable = await db.scalar(
        select(Timetable)
        .where(Timetable.season_id == season_id, Timetable.game_id == game.id)
        .order_by(Timetable.order_index)
    )
    if timetable is None:
        raise QuizSeedError(
            f"선택한 시즌의 타임테이블에 '{game_title}' 항목이 없습니다. 먼저 타임테이블에 추가하세요."
        )

    session = await db.scalar(
        select(GameSession)
        .where(GameSession.timetable_id == timetable.id)
        .order_by(GameSession.id.desc())
    )
    if session is not None:
        return session

    if not create_session:
        raise QuizSeedError(
            f"'{game_title}' 세션이 없습니다. '세션 없으면 생성'을 켜고 다시 시도하세요."
        )

    session = GameSession(timetable_id=timetable.id, state="idle", updated_by=admin_id)
    db.add(session)
    await db.flush()
    return session


async def _clear_waiting_rounds(db: AsyncSession, session_id: int) -> int:
    """제출 기록이 없는 대기(waiting) 라운드를 삭제하고 삭제 수를 반환."""
    rounds = (
        await db.scalars(
            select(GameRound).where(
                GameRound.session_id == session_id, GameRound.status == "waiting"
            )
        )
    ).all()
    removed = 0
    for r in rounds:
        has_submission = await db.scalar(
            select(RoundSubmission.id).where(RoundSubmission.round_id == r.id).limit(1)
        )
        if has_submission is not None:
            continue  # 진행 이력이 있으면 보존
        await db.delete(r)
        removed += 1
    await db.flush()
    return removed


async def seed_rounds(
    db: AsyncSession,
    *,
    season_id: int,
    admin_id: int | None,
    categories: list[str] | None = None,
    limit: int | None = None,
    shuffle: bool = False,
    create_session: bool = False,
    replace: bool = False,
    session_id: int | None = None,
    game_title: str = DEFAULT_GAME_TITLE,
) -> dict:
    """선택한 문제를 '퀴즈 대결' 세션에 대기 라운드로 적재.

    Returns: {seeded, session_id, start_order, removed}
    """
    errors = validate()
    if errors:
        raise QuizSeedError("문제 데이터 검증 실패: " + "; ".join(errors[:3]))

    questions = _select_questions(categories, limit, shuffle)
    if not questions:
        raise QuizSeedError("선택된 문제가 없습니다. (카테고리/필터 확인)")

    session = await _resolve_session(
        db,
        season_id=season_id,
        game_title=game_title,
        session_id=session_id,
        create_session=create_session,
        admin_id=admin_id,
    )

    removed = 0
    if replace:
        removed = await _clear_waiting_rounds(db, session.id)

    start_order = (
        await db.scalar(
            select(func.coalesce(func.max(GameRound.order_index), 0)).where(
                GameRound.session_id == session.id
            )
        )
    ) or 0

    for offset, q in enumerate(questions, start=1):
        db.add(
            GameRound(
                session_id=session.id,
                order_index=start_order + offset,
                status="waiting",
                prompt=q.prompt,
                options=list(q.options),
                correct_answer=q.answer,
                created_by=admin_id,
            )
        )
    await db.commit()

    return {
        "seeded": len(questions),
        "session_id": session.id,
        "start_order": start_order + 1,
        "removed": removed,
    }
