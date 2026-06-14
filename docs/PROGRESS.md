# Workshop Backend — 개발 진행 정리

가평 워크샵 웹 프로젝트 백엔드. 게임 진행·점수·추첨·실시간 중계를 담당하는 운영 서버.

> 이 문서는 초기 스캐폴드 이후 진행한 작업 전체를 정리한 기록입니다.
> (PR #1 ~ #10, 모두 `main` 에 머지됨)

---

## 1. 기술 스택

| 영역 | 사용 |
|------|------|
| 웹 프레임워크 | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 (async) |
| DB | PostgreSQL (asyncpg 드라이버) |
| 마이그레이션 | Alembic 1.13 (async 템플릿) |
| 인증 | JWT (python-jose) + bcrypt |
| 실시간 | WebSocket (Starlette) |
| 테스트 | pytest + pytest-asyncio + httpx |

---

## 2. 디렉토리 구조

```
app/
├── api/              REST 라우터 (auth, season, team, user, game,
│                     timetable, game_session, score, result, roulette)
├── core/             config(환경변수), security(JWT·bcrypt)
├── db/               base(Base·Mixin), session(AsyncSession)
├── models/           SQLAlchemy 모델 19개 + relationship
├── schemas/          Pydantic 요청/응답 스키마
├── services/         비즈니스 로직 (라우터에서 분리)
├── websocket/        manager(연결관리), endpoint(/ws),
│                     handlers(메시지 dispatch), events(브로드캐스트)
└── main.py           FastAPI 진입점 (라우터 등록)
alembic/              마이그레이션 (v2 초기 스키마)
scripts/              create_admin.py (초기 admin 생성 CLI)
tests/                pytest (69개)
```

---

## 3. 데이터 모델 (v2 스키마)

`workshop_schema_v2.sql` 기준으로 **19개 테이블**을 SQLAlchemy 모델로 구현.
CHECK 제약·server_default·FK 제약명·컬럼 comment 까지 DDL 과 1:1 일치.

**핵심 테이블**
- `seasons` / `teams` / `users` — 시즌·팀·유저 (계층)
- `game` / `timetable` / `game_sessions` — 게임 정의 · 진행표 · 세션
- `game_score_logs` / `game_results` / `game_chat_logs` — 점수·결과·채팅
- `rewards` / `buff` / `envelopes` / `raffle_tickets` / `team_buffs` — 보상·버프·봉투·뽑기권
- `hidden_roles` / `user_hidden_roles` — 히든롤
- `vote_items` / `vote_ballots` / `vote_records` — 투표

**relationship**: 핵심 도메인 관계를 `relationship()` 으로 연결 (ORM 탐색용, DB 스키마 변경 없음).
`user.team.season` 처럼 객체로 체이닝 가능. 감사 컬럼(`created_by`/`updated_by`)은 모호성 방지를 위해 관계 제외.

**마이그레이션 특이사항**: `seasons ↔ users ↔ teams` 순환 FK 때문에, 초기 마이그레이션에서
`seasons → users` FK 2개를 테이블 생성 후 별도 `create_foreign_key` 로 분리 (downgrade 도 대응).

---

## 4. 인증 / 권한

- `POST /api/auth/login` — username/password → JWT 발급
- `GET /api/auth/me` — 토큰으로 본인 조회
- 의존성: `CurrentUser`(로그인 필요) / `AdminUser`(운영자 권한)
- 비밀번호 해시는 **bcrypt 직접 사용** (passlib 1.7.4 ↔ bcrypt 5.x 비호환 이슈로 전환)
- 초기 admin 은 `python -m scripts.create_admin` CLI 로 생성 (재실행 안전)

---

## 5. REST API (35개 엔드포인트)

읽기는 로그인 유저, **쓰기는 운영자(admin)** 전용.

### Season / Team
| Method | Path |
|--------|------|
| POST/GET | `/api/seasons` |
| GET/PATCH | `/api/seasons/{id}` (상태 active→started_at, done→ended_at 자동 기록) |
| POST/GET | `/api/seasons/{id}/teams` |
| GET/PATCH | `/api/teams/{id}` |

### User
| Method | Path |
|--------|------|
| POST/GET | `/api/users` (username 중복 409, role 422, team 400, 필터 role/team_id) |
| GET/PATCH | `/api/users/{id}` (비밀번호 변경 시 재해시, 부분수정) |

### Game / Timetable
| Method | Path |
|--------|------|
| POST/GET | `/api/games` (participant_type·input_type Literal 검증) |
| GET/PATCH | `/api/games/{id}` |
| POST/GET | `/api/seasons/{id}/timetable` (order_index 정렬, 시즌 404·게임 400) |
| GET/PATCH | `/api/timetable/{id}` |

### Game Session (상태 머신)
| Method | Path |
|--------|------|
| POST | `/api/timetable/{id}/session` (세션 생성, idle) |
| GET | `/api/timetable/{id}/sessions` |
| GET | `/api/sessions/{id}` |
| POST | `/api/sessions/{id}/transition` `{to}` |

### Score / Result
| Method | Path |
|--------|------|
| POST/GET | `/api/sessions/{id}/scores` (subject team/user, 대상검증) |
| GET | `/api/sessions/{id}/scores/summary` (subject별 합산 집계) |
| PATCH | `/api/scores/{id}` |
| POST/GET | `/api/sessions/{id}/results` |

### Roulette (provably-fair)
| Method | Path |
|--------|------|
| GET | `/api/sessions/{id}/roulette/commitment` |
| POST | `/api/sessions/{id}/roulette/spin` `{options, nonce}` |
| GET | `/api/sessions/{id}/roulette/seed` (done 후에만) |

---

## 6. 게임 세션 상태 머신

```
idle → ready → in_progress → scoring → reward → done
                                  └────────────→ done   (보상 단계 생략 가능)
```

- 명시적 전이 맵으로 검증 → 허용 안 된 전이는 `409` + 가능한 전이 안내, 잘못된 값은 `422`
- **부수효과**: `in_progress` 진입 시 `started_at` 기록 + **서버 시드(seed) 생성**,
  `done` 진입 시 `ended_at` 기록
- 시드는 결과 예측 악용 방지를 위해 일반 응답에 미노출

---

## 7. WebSocket (`/ws?token=...`)

- 연결 시 JWT 인증, `ConnectionManager` 로 개인/팀/전체 브로드캐스트
- **메시지 핸들러 분리**: `handlers.py` 의 레지스트리 + `dispatch()` 라우팅
  (`@register("type")` 데코레이터로 확장, 미지원 타입은 error 응답)
- **서버 → 클라이언트 이벤트** (`events.py`): REST 동작이 접속자에게 실시간 푸시
  - `session_state_changed` — 세션 상태 전이
  - `score_recorded` / `result_recorded` — 점수·결과 기록 (라이브 스코어보드)
  - `roulette_result` — 룰렛 추첨 결과

---

## 8. 검증 가능한(provably-fair) 룰렛/추첨

**commit-reveal** 방식으로 추첨 공정성을 보장:

1. **commitment** = `sha256(seed)` 를 추첨 전에 공개 (조작 불가 약속)
2. **spin** = `HMAC-SHA256(seed, nonce)` → 결정론적 선택 (같은 입력 → 항상 같은 결과)
3. **seed 공개** = 게임 종료 후에만 → 누구나 결과를 재계산해 검증

RNG 코어(`roulette_service`)는 순수 함수라 단위 테스트로 완전 검증.

---

## 9. 테스트 (69개, 전부 통과)

```bash
pip install -r requirements-dev.txt
pytest
```

| 파일 | 범위 |
|------|------|
| `test_auth_e2e.py` | 로그인 → /me, 인증 실패 |
| `test_season_team.py` | 시즌·팀 CRUD, 상태전이, 권한 |
| `test_user_management.py` | 유저 생성/수정/필터, 비번변경 후 로그인 |
| `test_relationships.py` | relationship 양방향 탐색 |
| `test_game_timetable.py` | 게임·타임테이블 CRUD, 정렬 |
| `test_game_session.py` | 상태 머신 수명주기, 시드 생성 |
| `test_websocket.py` | dispatch, 실제 WS 연결, 브로드캐스트 |
| `test_score_result.py` | 점수·결과 기록, 합산 집계 |
| `test_roulette.py` | 결정론 RNG, commit-reveal |

테스트는 `.env` 의 DB(`workshop_26`)에 붙는 E2E 방식. ASGITransport(httpx)로 앱 직접 호출.

---

## 10. 실행 방법

```bash
# 1. 가상환경 + 의존성
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. 환경변수
cp .env.example .env   # DATABASE_URL, SECRET_KEY 설정

# 3. DB 마이그레이션
alembic upgrade head

# 4. 초기 운영자 생성
python -m scripts.create_admin --username admin --password <pw> --nickname 운영자

# 5. 서버 실행
uvicorn app.main:app --reload --port 8000
#  - Swagger: http://localhost:8000/docs
```

---

## 11. PR 히스토리

| PR | 내용 |
|----|------|
| #1 | v2 스키마 모델 + Alembic 초기 마이그레이션 |
| #2 | 인증 플로우 E2E 테스트 (pytest 도입) |
| #3 | Season·Team 관리 API |
| #4 | 유저 생성/관리 API |
| #5 | 모델 relationship 정리 |
| #6 | 게임 정의 / 타임테이블 관리 API |
| #7 | 게임 세션 상태 머신 |
| #8 | WebSocket 핸들러 분리 + 상태 전이 브로드캐스트 |
| #9 | 점수/결과 기록 API + 라이브 브로드캐스트 |
| #10 | 검증 가능한(provably-fair) 룰렛/추첨 |

---

## 12. 남은 작업 (후보)

- WebSocket 채팅 핸들러 (`chat` 타입 + `game_chat_logs` 저장 + 정답 판정)
- 봉투(envelope) 뽑기 API (룰렛 로직 ↔ raffle_tickets/rewards 연결)
- 버프/디버프, 히든롤, 투표 운영 API
- CORS 도메인 좁히기 (현재 `allow_origins=["*"]`)
- CI (GitHub Actions 로 pytest 자동 실행)
