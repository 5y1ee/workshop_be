"""DB 초기화 + 데모 시드 스크립트.

테스트가 운영 DB 에 쌓아둔 더미를 정리하고, 깨끗한 초기 데이터를 넣는다.
**대상은 .env 의 DATABASE_URL (운영 DB)** 이므로 파괴적 작업에는 --yes 가 필요하다.

사용법:
    python -m scripts.seed_db reset --yes        # 전체 테이블 drop + create
    python -m scripts.seed_db seed               # 데모 데이터 삽입 (비어있을 때만)
    python -m scripts.seed_db reset-seed --yes   # 초기화 후 시드까지 한 번에

기본 계정: admin / admin1234,  참가자 예시 로그인: trainer / trainer1234
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models.game import Game
from app.models.game_session import GameResult, GameScoreLog, GameSession
from app.models.reward import Reward
from app.models.season import Season
from app.models.team import Team
from app.models.timetable import Timetable
from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _target_db() -> str:
    # postgresql+asyncpg://user:pw@host:port/<db>
    return settings.DATABASE_URL.rsplit("/", 1)[-1]


async def reset() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print(f"✅ reset 완료 — '{_target_db()}' 의 모든 테이블 drop + create")


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(func.count()).select_from(Season))).scalar()
        if existing and existing > 0:
            print(f"⚠️  이미 시즌이 {existing}개 있습니다. 먼저 reset 하세요. (시드 중단)")
            return

        now = _utcnow()

        # --- 운영자 ---
        admin = User(
            username="admin",
            password=hash_password("admin1234"),
            nickname="운영자",
            role="admin",
        )
        db.add(admin)
        await db.flush()  # admin.id 확보 (created_by 용)

        # --- 시즌 ---
        season = Season(name="가평 워크샵 2026", status="active", created_by=admin.id)
        db.add(season)
        await db.flush()

        # --- 팀 4개 ---
        team_names = ["🔴 레드팀", "🔵 블루팀", "🟢 그린팀", "🟡 옐로팀"]
        teams = [Team(season_id=season.id, name=n) for n in team_names]
        db.add_all(teams)
        await db.flush()

        # --- 참가자: 팀당 3명 (12명), 첫 명은 로그인 계정 trainer ---
        nicknames = [
            ["아론", "지나", "현우"],
            ["민수", "서연", "도윤"],
            ["하준", "수아", "지호"],
            ["예준", "유나", "건우"],
        ]
        points = [[40, 25, 15], [30, 20, 10], [22, 18, 12], [16, 14, 9]]
        for ti, team in enumerate(teams):
            for ui, nick in enumerate(nicknames[ti]):
                uname = "trainer" if (ti == 0 and ui == 0) else f"p{ti}{ui}"
                pw = "trainer1234" if uname == "trainer" else "pw12345678"
                db.add(
                    User(
                        username=uname,
                        password=hash_password(pw),
                        nickname=nick,
                        role="user",
                        team_id=team.id,
                        point=points[ti][ui],
                    )
                )

        # --- 게임 5개 ---
        games_def = [
            ("몸으로 말해요", "제스처로 단어 맞히기", "team_vs", "offline"),
            ("퀴즈 대결", "버저 누르고 정답", "team_vs", "button"),
            ("노래 맞추기", "채팅으로 제목 입력", "team_vs", "chat"),
            ("보물찾기", "개인전 미션", "individual", "offline"),
            ("릴레이 게임", "대표자 릴레이", "representative", "button"),
        ]
        games = [
            Game(title=t, description=d, participant_type=p, input_type=i)
            for t, d, p, i in games_def
        ]
        db.add_all(games)
        await db.flush()

        # --- 타임테이블 5개 ---
        entries = [
            Timetable(
                season_id=season.id,
                game_id=games[idx].id,
                order_index=idx + 1,
                label=f"{idx + 1}. {games[idx].title}",
            )
            for idx in range(len(games))
        ]
        db.add_all(entries)
        await db.flush()

        # --- 세션: 2개 종료(점수+결과), 1개 진행중, 2개 대기 ---
        sessions = []
        for idx, entry in enumerate(entries):
            if idx < 2:
                state, seed_v = "done", secrets.token_hex(16)
                started, ended = now - timedelta(hours=2 - idx), now - timedelta(hours=1)
            elif idx == 2:
                state, seed_v = "in_progress", secrets.token_hex(16)
                started, ended = now - timedelta(minutes=10), None
            else:
                state, seed_v, started, ended = "idle", None, None, None
            s = GameSession(
                timetable_id=entry.id,
                state=state,
                seed=seed_v,
                started_at=started,
                ended_at=ended,
            )
            sessions.append(s)
        db.add_all(sessions)
        await db.flush()

        # --- 점수/결과: 종료 2세션 + 진행중 1세션 ---
        # 종료 세션 0: 레드 35, 블루 20, 그린 10  → 레드 우승
        # 종료 세션 1: 블루 30, 그린 25, 옐로 15  → 블루 우승
        # 진행중 세션 2: 레드 5, 블루 8 (집계 중)
        score_plan = [
            (0, [(teams[0], 35), (teams[1], 20), (teams[2], 10)], teams[0]),
            (1, [(teams[1], 30), (teams[2], 25), (teams[3], 15)], teams[1]),
            (2, [(teams[0], 5), (teams[1], 8)], None),
        ]
        for sidx, rows, winner in score_plan:
            for team, sc in rows:
                db.add(
                    GameScoreLog(
                        session_id=sessions[sidx].id,
                        subject_type="team",
                        subject_id=team.id,
                        score=sc,
                        created_by=admin.id,
                    )
                )
            if winner is not None:
                db.add(
                    GameResult(
                        session_id=sessions[sidx].id,
                        subject_type="team",
                        subject_id=winner.id,
                    )
                )

        # --- 리워드 도감 6개 (3 공개 / 3 실루엣) ---
        rewards_def = [
            ("신세계 상품권 5만원", "백화점 어디서나 5만원", 2, "https://img/giftcard.png"),
            ("BBQ 황금올리브", "치킨 기프티콘", 5, "https://img/chicken.png"),
            ("스타벅스 아메리카노", "T 사이즈 쿠폰", 10, "https://img/coffee.png"),
            ("에어팟 프로 2", "미공개 한정 보상", 1, None),
            ("배민 상품권 3만원", "미공개", 3, None),
            ("미스터리 박스", "???", 1, None),
        ]
        for name, desc, total, img in rewards_def:
            db.add(
                Reward(name=name, description=desc, total_count=total, image_url=img)
            )

        await db.commit()

    print("✅ seed 완료")
    print("   - 시즌 '가평 워크샵 2026' (active)")
    print("   - 팀 4 / 참가자 12 / 게임 5 / 타임테이블 5")
    print("   - 세션: 종료 2(점수+결과), 진행중 1, 대기 2")
    print("   - 리워드 6 (공개 3 / 실루엣 3)")
    print("   - 로그인: admin/admin1234, trainer/trainer1234")


def _require_yes(args, action: str) -> None:
    if not args.yes:
        print(
            f"⛔ '{action}' 는 '{_target_db()}' DB 를 파괴적으로 변경합니다.\n"
            f"   실행하려면 --yes 를 붙이세요:  python -m scripts.seed_db {action} --yes"
        )
        sys.exit(1)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="DB 초기화 + 데모 시드")
    parser.add_argument("command", choices=["reset", "seed", "reset-seed"])
    parser.add_argument("--yes", action="store_true", help="파괴적 작업 확인")
    args = parser.parse_args()

    print(f"대상 DB: {_target_db()}")
    try:
        if args.command == "reset":
            _require_yes(args, "reset")
            await reset()
        elif args.command == "seed":
            await seed()
        elif args.command == "reset-seed":
            _require_yes(args, "reset-seed")
            await reset()
            await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
