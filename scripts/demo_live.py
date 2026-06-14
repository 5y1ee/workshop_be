"""라이브 스코어보드 데모 드라이버.

(A) 깨끗한 데모 시즌 한 세트를 만들고, FE를 띄워둔 상태에서
점수/상태전이/룰렛 이벤트를 순서대로 발사해 실시간 갱신을 눈으로 확인한다.

사용법:
    python -m scripts.demo_live setup          # 데모 시즌+팀+게임+타임테이블+세션 생성
    python -m scripts.demo_live drive <id>     # 해당 세션에 라이브 이벤트 발사

표준 라이브러리만 사용 (urllib). 백엔드가 :8000 에 떠 있어야 한다.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://localhost:8000"
ADMIN_USER = "admin"
ADMIN_PASS = "admin1234"


def _req(method: str, path: str, token: str | None = None, body: dict | None = None) -> dict | list:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as res:
            raw = res.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        print(f"  ! HTTP {e.code} {method} {path}\n    {detail}", file=sys.stderr)
        raise


def login() -> str:
    res = _req("POST", "/api/auth/login", body={"username": ADMIN_USER, "password": ADMIN_PASS})
    return res["access_token"]


def setup() -> None:
    token = login()
    stamp = time.strftime("%H%M%S")
    season = _req("POST", "/api/seasons", token, {"name": f"🎬 데모시즌 {stamp}"})
    sid = season["id"]
    teams = [
        _req("POST", f"/api/seasons/{sid}/teams", token, {"name": name})
        for name in ("🔴 레드팀", "🔵 블루팀", "🟢 그린팀")
    ]
    game = _req(
        "POST", "/api/games", token,
        {"title": "데모 미니게임", "participant_type": "team_vs", "input_type": "button"},
    )
    entry = _req(
        "POST", f"/api/seasons/{sid}/timetable", token,
        {"game_id": game["id"], "order_index": 1, "label": "1. 데모 미니게임"},
    )
    session = _req("POST", f"/api/timetable/{entry['id']}/session", token)

    print("\n✅ 데모 데이터 생성 완료\n")
    print(f"   시즌 이름 : {season['name']}")
    print(f"   세션 ID   : {session['id']}  (상태: {session['state']})")
    print(f"   팀        : " + ", ".join(f"{t['name']}#{t['id']}" for t in teams))
    print("\n다음 단계:")
    print(f"   1) FE에서 '{season['name']}' → '1. 데모 미니게임' → '세션 #{session['id']}' 선택")
    print(f"   2) python -m scripts.demo_live drive {session['id']}")
    # 팀 ID 를 drive 단계에서 쓰도록 출력
    print("\n   (drive 시 자동으로 이 시즌의 팀을 찾아 점수를 매깁니다.)")


def _teams_for_session(token: str, session_id: int) -> list[dict]:
    session = _req("GET", f"/api/sessions/{session_id}", token)
    entry = _req("GET", f"/api/timetable/{session['timetable_id']}", token)
    return _req("GET", f"/api/seasons/{entry['season_id']}/teams", token)


def _step(msg: str, pause: float = 2.5) -> None:
    print(f"  → {msg}")
    time.sleep(pause)


def drive(session_id: int) -> None:
    token = login()
    teams = _teams_for_session(token, session_id)
    if len(teams) < 2:
        print("팀이 부족합니다. setup 을 먼저 실행하세요.", file=sys.stderr)
        sys.exit(1)

    print(f"\n🎬 세션 #{session_id} 라이브 시작 — FE 화면을 보세요!\n")

    _step("상태 전이: → ready")
    _req("POST", f"/api/sessions/{session_id}/transition", token, {"to": "ready"})

    _step("상태 전이: → in_progress (시드 생성)")
    _req("POST", f"/api/sessions/{session_id}/transition", token, {"to": "in_progress"})

    # 점수를 라운드로 나눠 누적 → 스코어보드 순위가 실시간으로 바뀜
    rounds = [
        (teams[0]["id"], 10),
        (teams[1]["id"], 15),
        (teams[2 % len(teams)]["id"], 8),
        (teams[1]["id"], 20),
        (teams[0]["id"], 25),
    ]
    for i, (team_id, score) in enumerate(rounds, 1):
        name = next(t["name"] for t in teams if t["id"] == team_id)
        _step(f"점수 기록 R{i}: {name} +{score}")
        _req(
            "POST", f"/api/sessions/{session_id}/scores", token,
            {"subject_type": "team", "subject_id": team_id, "score": score, "memo": f"R{i}"},
        )

    _step("상태 전이: → scoring")
    _req("POST", f"/api/sessions/{session_id}/transition", token, {"to": "scoring"})

    _step("🎰 룰렛 스핀")
    options = [t["name"] for t in teams]
    spin = _req(
        "POST", f"/api/sessions/{session_id}/roulette/spin", token,
        {"options": options, "nonce": 1},
    )
    print(f"     당첨: {spin['selected']}  (commitment={spin['commitment'][:12]}…)")
    time.sleep(2.5)

    _step("상태 전이: → done", pause=1.0)
    _req("POST", f"/api/sessions/{session_id}/transition", token, {"to": "done"})

    print("\n✅ 라이브 종료. FE 이벤트 로그와 스코어보드가 갱신됐는지 확인하세요.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="라이브 스코어보드 데모 드라이버")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup", help="데모 시즌 한 세트 생성")
    d = sub.add_parser("drive", help="세션에 라이브 이벤트 발사")
    d.add_argument("session_id", type=int)
    args = parser.parse_args()

    if args.cmd == "setup":
        setup()
    elif args.cmd == "drive":
        drive(args.session_id)


if __name__ == "__main__":
    main()
