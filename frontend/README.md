# Workshop Frontend

가평 워크샵 모바일 웹 (React + TypeScript + Vite). 로그인 + 라이브 스코어보드.

## 실행

```bash
cd frontend
npm install
cp .env.example .env      # 필요 시 VITE_API_BASE 수정 (기본 http://localhost:8000)
npm run dev               # http://localhost:5173
```

백엔드(`uvicorn app.main:app --port 8000`)가 떠 있어야 하며,
로그인할 유저는 `python -m scripts.create_admin` 등으로 미리 생성해야 합니다.

## 구성

- `src/api.ts` — REST 클라이언트 + 타입
- `src/auth.tsx` — JWT 저장(localStorage) 컨텍스트
- `src/useWebSocket.ts` — `/ws` 실시간 연결 훅
- `src/pages/LoginPage.tsx` — 로그인
- `src/pages/ScoreboardPage.tsx` — 시즌→게임→세션 선택 + 합산 스코어보드 + 실시간 이벤트

## 실시간 이벤트

세션 상태 전이, 점수/결과 기록, 룰렛 결과를 WebSocket 으로 수신해
스코어보드를 자동 갱신하고 이벤트 로그를 표시합니다.
