# Workshop Backend

가평 워크샵 웹 프로젝트. **FastAPI + SQLAlchemy(async) + PostgreSQL** 백엔드와
**React + TypeScript(Vite)** 모바일 프론트엔드로 구성된다.

시즌 단위로 팀을 나눠 여러 게임을 진행하고, 점수·결과·리워드·룰렛을 운영자가
관리하며 참가자는 실시간 스코어보드를 본다.

## 디렉토리 구조

```
app/
├── api/              REST API 라우터
│   ├── auth.py         인증 (login)
│   ├── season.py team.py user.py
│   ├── game.py timetable.py game_session.py   게임/타임테이블/세션 상태머신
│   ├── score.py result.py                      점수·결과·시즌 스코어보드
│   ├── reward.py                               리워드 도감
│   ├── roulette.py                             공정성 검증 룰렛
│   └── deps.py         공통 의존성 (인증/권한)
├── core/             config(환경변수), security(JWT·bcrypt)
├── db/               base(Base·Mixin), session(AsyncSession)
├── models/           SQLAlchemy 모델 (user, season, team, game, timetable,
│                     game_session, reward, buff, envelope, raffle, hidden_role, vote)
├── schemas/          Pydantic 요청/응답 스키마
├── services/         비즈니스 로직 (라우터에서 분리)
├── websocket/        manager(broadcast), handlers(dispatch), endpoint(/ws), events
└── main.py           FastAPI 진입점

frontend/             React + TS 모바일 앱 (로그인 + 5탭 포켓몬 UI)
scripts/              create_admin, seed_db(초기화/시드), demo_live(라이브 데모)
alembic/              마이그레이션
docs/                 진행 정리·화면 기획서
```

## 실행 (백엔드)

**Python 3.10 이상** 필요 (권장: 3.12).

### 1. 가상환경 + 의존성

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 환경변수

```bash
cp .env.example .env
# .env 편집: DATABASE_URL, SECRET_KEY 등
```

### 3. DB 마이그레이션

```bash
alembic upgrade head
```

### 4. 초기 데이터 시드 (선택)

빈 DB 에 데모 데이터(시즌·팀·참가자·게임·세션·리워드)를 한 번에 채운다.
**대상은 `.env` 의 `DATABASE_URL`(운영 DB)이며, 파괴적 작업이라 `--yes` 가 필요하다.**

```bash
python -m scripts.seed_db reset-seed --yes   # 전체 초기화 후 데모 시드
# 개별 실행도 가능
python -m scripts.seed_db reset --yes        # 모든 테이블 drop + create
python -m scripts.seed_db seed               # 비어있을 때만 데모 데이터 삽입
```

시드 결과: 활성 시즌 1 · 팀 3(6명씩) · 참가자 18 · 게임 5 · 타임테이블 5 ·
세션(종료 2/진행 1/대기 2) · 리워드 6(공개 3/실루엣 3).
로그인 예시 — 관리자 `sangyoon`/`sangyoon1234`, 참가자 `sanghee`/`sanghee1234`
(비밀번호는 모두 `<아이디>1234`).

### 5. 서버 실행

```bash
uvicorn app.main:app --reload --port 8000
```

- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 실행 (프론트엔드)

```bash
cd frontend
npm install
cp .env.example .env       # 필요 시 VITE_API_BASE 수정 (기본 http://localhost:8000)
npm run dev                # http://localhost:5173
```

백엔드가 `:8000` 에 떠 있어야 한다. 로그인 후 하단 5탭(마이/랭킹/메인/도감/미니)으로
구성된 모바일 화면이 뜬다. 운영자(admin) 계정은 게임 상세에서 운영자 패널
(상태 전이·점수 입력·룰렛)을 사용할 수 있다.

## 테스트

```bash
pytest -v
```

테스트는 **운영 DB 를 절대 건드리지 않는다.** `DATABASE_URL` 의 DB 이름에 `_test`
를 붙인 별도 DB(예: `workshop_26_test`)를 자동 생성하고, 매 실행 시작 시
`drop_all + create_all` 로 스키마를 초기화한 뒤 거기서만 실행된다.
DB 이름은 `TEST_DATABASE_NAME` 환경변수로 바꿀 수 있다.

## WebSocket 연결

```javascript
const token = "발급받은 JWT";
const ws = new WebSocket(`ws://localhost:8000/ws?token=${token}`);

ws.onmessage = (e) => console.log(JSON.parse(e.data));
ws.send(JSON.stringify({ type: "ping" }));
```

세션 상태 전이·점수/결과 기록·룰렛 결과가 실시간으로 브로드캐스트된다.

## 다음 단계

- [ ] 리워드 운영 CRUD + 공개(is_revealed) 플래그
- [ ] 개인(유저) 랭킹 집계
- [ ] WebSocket 채팅 (game_chat_logs)
- [ ] 봉투/버프/히든롤/투표 API
- [ ] CORS 도메인 제한 + 배포
- [ ] CI (pytest + frontend build)
