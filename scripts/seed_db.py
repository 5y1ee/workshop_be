"""DB 초기화 + 데모 시드 스크립트.

테스트가 운영 DB 에 쌓아둔 더미를 정리하고, 깨끗한 초기 데이터를 넣는다.
**대상은 .env 의 DATABASE_URL (운영 DB)** 이므로 파괴적 작업에는 --yes 가 필요하다.

사용법:
    python -m scripts.seed_db reset --yes        # 전체 테이블 drop + create
    python -m scripts.seed_db seed               # 데모 데이터 삽입 (비어있을 때만)
    python -m scripts.seed_db reset-seed --yes   # 초기화 후 시드까지 한 번에

기본 계정: sangyoon / sangyoon1234 (관리자), 참가자 예시: sanghee / sanghee1234
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
from app.models.game_round import GameRound
from app.models.game_session import GameResult, GameScoreLog, GameSession
from app.models.reward import Reward
from app.models.season import Season
from app.models.team import Team
from app.models.team_member import TeamMembership
from app.models.timetable import Timetable
from app.models.user import User

# (화면 이름, 로그인 ID, 포켓몬, 권한, 개인 포인트) — 팀은 목록 순서대로 6명씩 배치
PARTICIPANTS: list[tuple[str, str, str, str, int]] = [
    ("나상희", "sanghee", "찌리리공", "user", 40),
    ("김현진", "hyunjin", "파이숭이", "user", 25),
    ("이승민", "seungmin", "어니부기", "user", 15),
    ("양준석", "junseok", "야돈", "user", 12),
    ("임지호", "jiho", "근육몬", "user", 10),
    ("정소희", "sohee", "모다피", "user", 8),
    ("박민지", "minji", "마자용", "admin", 35),
    ("이소민", "somin", "치코리타", "admin", 30),
    ("이상윤", "sangyoon", "네이티오", "admin", 28),
    ("신윤섭", "yunseop", "이상해씨", "user", 20),
    ("황지선", "jiseon", "아르코", "user", 18),
    ("유태영", "taeyoung", "파오리", "user", 14),
    ("양수빈", "subin", "펭도리", "user", 22),
    ("김소연", "soyeon", "꼬리선", "user", 20),
    ("박재한", "jaehan", "고라파덕", "user", 16),
    ("여민호", "minho", "슈륙챙이", "user", 12),
    ("김민우", "minwoo", "잠만보", "user", 10),
    ("장승연", "seungyeon", "에브이", "user", 8),
]

TEAM_NAMES = ["🔴 레드팀", "🔵 블루팀", "🟢 그린팀"]
TEAM_SIZE = 6
BOOTSTRAP_ADMIN = "sangyoon"


def _profile_image(pokemon: str, nickname: str) -> str:
    return f"/resources/{pokemon}_{nickname}.png"


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

        # --- 시즌 생성자 (created_by 용) ---
        bootstrap = next(p for p in PARTICIPANTS if p[1] == BOOTSTRAP_ADMIN)
        bn, bu, bp, br, bpt = bootstrap
        admin = User(
            username=bu,
            password=hash_password(f"{bu}1234"),
            nickname=bn,
            role=br,
            point=bpt,
            profile_image=_profile_image(bp, bn),
        )
        db.add(admin)
        await db.flush()

        # --- 시즌 ---
        season = Season(name="가평 워크샵 2026", status="active", created_by=admin.id)
        db.add(season)
        await db.flush()

        # --- 팀 3개 (6명씩) ---
        teams = [Team(season_id=season.id, name=n) for n in TEAM_NAMES]
        db.add_all(teams)
        await db.flush()

        # --- 참가자 18명 (팀 배정은 멤버십으로) ---
        membership_plan: list[tuple[User, Team]] = []
        for i, (nickname, username, pokemon, role, point) in enumerate(PARTICIPANTS):
            team = teams[i // TEAM_SIZE]
            if username == BOOTSTRAP_ADMIN:
                membership_plan.append((admin, team))
                continue
            u = User(
                username=username,
                password=hash_password(f"{username}1234"),
                nickname=nickname,
                role=role,
                point=point,
                profile_image=_profile_image(pokemon, nickname),
            )
            db.add(u)
            membership_plan.append((u, team))
        await db.flush()

        # 시즌별 팀 배정 (team_members)
        for u, team in membership_plan:
            db.add(
                TeamMembership(season_id=season.id, team_id=team.id, user_id=u.id)
            )

        # --- 게임 8개 ---
        games_def = [
            ("몸으로 말해요", "제스처로 단어 맞히기", "team_vs", "offline"),
            ("퀴즈 대결", "버저 누르고 정답", "team_vs", "button"),
            ("노래 맞추기", "채팅으로 제목 입력", "team_vs", "chat"),
            ("보물찾기", "개인전 미션", "individual", "offline"),
            ("릴레이 게임", "대표자 릴레이", "representative", "button"),
            ("철인 3종", "99초 게임 · 실내외 · 팀전원", "team_vs", "offline"),
            ("신발 던지기", "실외 · 전원 예선 후 결승", "individual", "offline"),
            ("좀비게임", "백업 · 실내외 넓은 공간 · 전원", "individual", "offline"),
        ]
        games = [
            Game(title=t, description=d, participant_type=p, input_type=i)
            for t, d, p, i in games_def
        ]
        db.add_all(games)
        await db.flush()

        # --- 타임테이블 8개 ---
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

        # --- 세션 상태 ---
        #  idx 0: 종료(점수+결과)  | idx 1: button 진행중  | idx 2: chat 진행중  | 나머지 대기
        in_progress_idx = {1, 2}
        sessions = []
        for idx, entry in enumerate(entries):
            if idx == 0:
                state, seed_v = "done", secrets.token_hex(16)
                started, ended = now - timedelta(hours=2), now - timedelta(hours=1)
            elif idx in in_progress_idx:
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

        # --- 라운드(세션 내부 진행도): 진행중 button/chat 세션에 문제 4개씩, 1번 문제 open ---
        # idx 1 = 퀴즈 대결(button), idx 2 = 노래 맞추기(chat)
        button_rounds = [
            ("대한민국의 수도는?", ["서울", "부산", "인천", "대전"], "서울"),
            ("물의 화학식은?", ["CO2", "H2O", "O2", "NaCl"], "H2O"),
            ("무지개는 몇 가지 색?", ["5", "6", "7", "8"], "7"),
            ("태양계에서 가장 큰 행성은?", ["지구", "토성", "목성", "화성"], "목성"),
        ]
        chat_rounds = [
            ("이 노래 제목은? 🎵 (힌트: BTS, 봄을 노래)", "봄날"),
            ("이 노래 제목은? 🎵 (힌트: 아이유, 잔잔한 밤)", "밤편지"),
            ("이 노래 제목은? 🎵 (힌트: 버스커버스커, 봄 대표곡)", "벚꽃엔딩"),
            ("이 노래 제목은? 🎵 (힌트: 잔나비)", "주저하는 연인들을 위해"),
        ]

        def _round(session_id, order, prompt, options, answer):
            opened = order == 1  # 1번 문제만 열어둔 상태로 시드
            return GameRound(
                session_id=session_id,
                order_index=order,
                status="open" if opened else "waiting",
                prompt=prompt,
                options=options,
                correct_answer=answer,
                opened_at=now if opened else None,
                created_by=admin.id,
            )

        for i, (prompt, options, answer) in enumerate(button_rounds, start=1):
            db.add(_round(sessions[1].id, i, prompt, options, answer))
        for i, (prompt, answer) in enumerate(chat_rounds, start=1):
            db.add(_round(sessions[2].id, i, prompt, None, answer))

        # --- 점수/결과 ---
        # 종료 세션 0: 레드 35, 블루 20, 그린 10  → 레드 우승
        # 진행중 세션 1(button): 레드 10, 블루 5 (집계 중)
        # 진행중 세션 2(chat):   블루 8, 그린 4 (집계 중)
        score_plan = [
            (0, [(teams[0], 35), (teams[1], 20), (teams[2], 10)], teams[0]),
            (1, [(teams[0], 10), (teams[1], 5)], None),
            (2, [(teams[1], 8), (teams[2], 4)], None),
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
                Reward(
                    season_id=season.id,
                    name=name,
                    description=desc,
                    total_count=total,
                    image_url=img,
                )
            )

        await db.commit()

    print("✅ seed 완료")
    print("   - 시즌 '가평 워크샵 2026' (active)")
    print("   - 팀 3 / 참가자 18 / 게임 8 / 타임테이블 8")
    print("   - 세션: 종료 1(점수+결과), 진행중 2(button/chat 각 4라운드), 대기 5")
    print("   - 라운드: 퀴즈대결(button)·노래맞추기(chat) 각 4문제, 1번 문제 open")
    print("   - 리워드 6 (공개 3 / 실루엣 3)")
    print("   - 관리자: minji/minji1234, somin/somin1234, sangyoon/sangyoon1234")
    print("   - 참가자 예시: sanghee/sanghee1234")


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
