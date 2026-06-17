"""퀴즈 대결 라운드 시드 스크립트.

`scripts.quiz_data` 의 객관식 문제를 '퀴즈 대결' 세션에 GameRound(button 타입)로 적재한다.
seed_db 와 독립적으로 동작하며, 이미 시즌·게임·타임테이블·세션이 있는 운영 DB 에
**문제만** 추가/교체한다.

세션 결정 순서:
    1. --session-id 가 주어지면 그 세션을 사용
    2. 아니면 활성 시즌에서 --game (기본 '퀴즈 대결') 게임의 타임테이블 → 세션을 찾음
       (세션이 여러 개면 가장 최근 것, 없고 --create-session 이면 idle 세션 생성)

사용법:
    python -m scripts.seed_quiz list                         # 카테고리/문제 수 출력
    python -m scripts.seed_quiz seed                         # 전체 문제 적재
    python -m scripts.seed_quiz seed --category 수학 --category 과학
    python -m scripts.seed_quiz seed --limit 20 --shuffle    # 무작위 20문제
    python -m scripts.seed_quiz seed --session-id 3          # 특정 세션에 적재
    python -m scripts.seed_quiz seed --create-session        # 세션 없으면 생성
    python -m scripts.seed_quiz seed --replace --yes         # 기존 대기 라운드 삭제 후 적재
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
import app.models  # noqa: F401 — Base.metadata 에 전체 테이블 등록
from app.models.game import Game
from app.models.game_round import GameRound, RoundSubmission
from app.models.game_session import GameSession
from app.models.season import Season
from app.models.timetable import Timetable
from app.models.user import User
from scripts.quiz_data import (
    QUIZ_QUESTIONS,
    QuizQuestion,
    category_counts,
    validate,
)

DEFAULT_GAME_TITLE = "퀴즈 대결"


def _target_db() -> str:
    return settings.DATABASE_URL.rsplit("/", 1)[-1]


async def _resolve_admin_id(db: AsyncSession) -> int | None:
    """라운드 created_by 용 관리자 ID. 없으면 None (nullable 이라 허용)."""
    return await db.scalar(
        select(User.id).where(User.role == "admin").order_by(User.id).limit(1)
    )


async def _find_session(
    db: AsyncSession,
    *,
    session_id: int | None,
    game_title: str,
    create_session: bool,
    admin_id: int | None,
) -> GameSession | None:
    if session_id is not None:
        session = await db.scalar(
            select(GameSession).where(GameSession.id == session_id)
        )
        if session is None:
            print(f"⛔ session_id={session_id} 세션을 찾을 수 없습니다.")
        return session

    season = await db.scalar(
        select(Season).where(Season.status == "active").order_by(Season.id.desc())
    )
    if season is None:
        print("⛔ 활성(active) 시즌이 없습니다. 먼저 seed_db 로 시즌을 만드세요.")
        return None

    game = await db.scalar(select(Game).where(Game.title == game_title))
    if game is None:
        print(f"⛔ '{game_title}' 게임을 찾을 수 없습니다.")
        return None

    timetable = await db.scalar(
        select(Timetable)
        .where(Timetable.season_id == season.id, Timetable.game_id == game.id)
        .order_by(Timetable.order_index)
    )
    if timetable is None:
        print(
            f"⛔ 시즌 '{season.name}' 의 타임테이블에 '{game_title}' 항목이 없습니다."
        )
        return None

    session = await db.scalar(
        select(GameSession)
        .where(GameSession.timetable_id == timetable.id)
        .order_by(GameSession.id.desc())
    )
    if session is not None:
        return session

    if not create_session:
        print(
            f"⛔ '{game_title}' 타임테이블에 세션이 없습니다. "
            f"--create-session 으로 새 세션을 만들 수 있습니다."
        )
        return None

    session = GameSession(timetable_id=timetable.id, state="idle", updated_by=admin_id)
    db.add(session)
    await db.flush()
    print(f"🆕 세션 생성 (timetable_id={timetable.id}) → session_id={session.id}")
    return session


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


async def seed(
    *,
    session_id: int | None,
    game_title: str,
    categories: list[str] | None,
    limit: int | None,
    shuffle: bool,
    create_session: bool,
    replace: bool,
) -> None:
    errors = validate()
    if errors:
        print("❌ quiz_data 검증 실패 — 적재 중단:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    questions = _select_questions(categories, limit, shuffle)
    if not questions:
        print("⚠️  선택된 문제가 없습니다. (카테고리/필터 확인)")
        return

    async with AsyncSessionLocal() as db:
        admin_id = await _resolve_admin_id(db)
        session = await _find_session(
            db,
            session_id=session_id,
            game_title=game_title,
            create_session=create_session,
            admin_id=admin_id,
        )
        if session is None:
            sys.exit(1)

        if replace:
            removed = await _clear_waiting_rounds(db, session.id)
            print(f"🧹 기존 대기 라운드 {removed}개 삭제")

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
                    options=q.options,
                    correct_answer=q.answer,
                    created_by=admin_id,
                )
            )
        await db.commit()

    used = category_counts() if not categories else None
    print(f"✅ 퀴즈 라운드 {len(questions)}개 적재 완료 (session_id={session.id})")
    print(f"   - order_index {start_order + 1} ~ {start_order + len(questions)}")
    if categories:
        print(f"   - 카테고리 필터: {', '.join(categories)}")
    elif used:
        print("   - 카테고리: " + ", ".join(f"{c}({n})" for c, n in used.items()))


def _print_catalog() -> None:
    print(f"총 {len(QUIZ_QUESTIONS)} 문제")
    for cat, cnt in category_counts().items():
        print(f"  - {cat}: {cnt}문제")


async def _main() -> None:
    parser = argparse.ArgumentParser(description="퀴즈 대결 라운드 시드")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="카테고리/문제 수 출력")

    sp = sub.add_parser("seed", help="문제를 세션에 적재")
    sp.add_argument("--session-id", type=int, default=None, help="대상 세션 ID 직접 지정")
    sp.add_argument("--game", default=DEFAULT_GAME_TITLE, help="게임 제목 (기본: 퀴즈 대결)")
    sp.add_argument(
        "--category", action="append", default=None, help="카테고리 필터 (반복 가능)"
    )
    sp.add_argument("--limit", type=int, default=None, help="적재할 최대 문제 수")
    sp.add_argument("--shuffle", action="store_true", help="문제 순서 무작위 섞기")
    sp.add_argument(
        "--create-session", action="store_true", help="세션이 없으면 새로 생성"
    )
    sp.add_argument(
        "--replace", action="store_true", help="기존 대기 라운드 삭제 후 적재 (--yes 필요)"
    )
    sp.add_argument("--yes", action="store_true", help="파괴적 작업(--replace) 확인")

    args = parser.parse_args()

    if args.command == "list":
        _print_catalog()
        return

    if args.replace and not args.yes:
        print(
            f"⛔ '--replace' 는 '{_target_db()}' DB 의 대기 라운드를 삭제합니다.\n"
            f"   실행하려면 --yes 를 붙이세요."
        )
        sys.exit(1)

    print(f"대상 DB: {_target_db()}")
    try:
        await seed(
            session_id=args.session_id,
            game_title=args.game,
            categories=args.category,
            limit=args.limit,
            shuffle=args.shuffle,
            create_session=args.create_session,
            replace=args.replace,
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
