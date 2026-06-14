# Workshop Backend

가평 워크샵 웹 프로젝트 백엔드. FastAPI + SQLAlchemy + PostgreSQL.

## 디렉토리 구조

```
app/
├── api/              REST API 라우터
│   ├── auth.py         인증 (login, /me)
│   └── deps.py         공통 의존성 (인증, 권한 체크)
├── core/             핵심 설정
│   ├── config.py       환경변수 설정
│   └── security.py     JWT, 비밀번호 해시
├── db/               DB 세션 관리
│   ├── base.py         SQLAlchemy Base, TimestampMixin
│   └── session.py      AsyncSession 생성
├── models/           SQLAlchemy 모델
│   ├── user.py
│   ├── season.py
│   └── team.py
├── schemas/          Pydantic 스키마 (요청/응답)
│   ├── auth.py
│   └── user.py
├── services/         비즈니스 로직 (추후 추가)
├── websocket/        WebSocket 처리
│   ├── manager.py      커넥션 관리 + broadcast
│   └── endpoint.py     /ws 엔드포인트
└── main.py           FastAPI 진입점
```

## 실행

**Python 3.10 이상** 필요 (권장: 3.12). `pyenv`/`asdf` 사용 시 `.python-version` 참고.

### 1. 가상환경 + 의존성 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
# .env 편집해서 DATABASE_URL, SECRET_KEY 등 설정
```

### 3. DB 마이그레이션 (Alembic 초기 세팅 후)

```bash
alembic upgrade head
```

### 4. 서버 실행

```bash
uvicorn app.main:app --reload --port 8000
```

### 5. API 문서

- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## WebSocket 연결

```javascript
const token = "발급받은 JWT";
const ws = new WebSocket(`ws://localhost:8000/ws?token=${token}`);

ws.onmessage = (e) => console.log(JSON.parse(e.data));
ws.send(JSON.stringify({ type: "ping" }));
```

## 다음 단계

- [ ] Alembic 마이그레이션 초기 세팅
- [ ] 나머지 모델 추가 (game, timetable, game_sessions 등)
- [ ] 게임 상태 머신 서비스 구현
- [ ] WebSocket 메시지 핸들러 분리
- [ ] 룰렛/도박 로직 (서버 사이드 시드 기반)
- [ ] 운영자 admin API
