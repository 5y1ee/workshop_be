import { useState } from 'react'
import { api, ApiError, type GameState, type Team } from '../api'

// 백엔드 game_session_service.TRANSITIONS 의 FE 미러
const NEXT_STATES: Record<GameState, GameState[]> = {
  idle: ['ready'],
  ready: ['in_progress'],
  in_progress: ['scoring'],
  scoring: ['reward', 'done'],
  reward: ['done'],
  done: [],
}

const STATE_LABEL: Record<GameState, string> = {
  idle: '대기',
  ready: '준비',
  in_progress: '진행중',
  scoring: '채점',
  reward: '보상',
  done: '종료',
}

interface Props {
  token: string
  sessionId: number
  state: GameState
  teams: Team[]
  onStateChange: (s: GameState) => void
  onScored: () => void
}

export default function OperatorPanel({
  token,
  sessionId,
  state,
  teams,
  onStateChange,
  onScored,
}: Props) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [teamId, setTeamId] = useState<number | null>(teams[0]?.id ?? null)
  const [score, setScore] = useState('10')

  const [nonce, setNonce] = useState(1)
  const [spinResult, setSpinResult] = useState<string | null>(null)

  const run = async (fn: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const transition = (to: GameState) =>
    run(async () => {
      const s = await api.transition(token, sessionId, to)
      onStateChange(s.state as GameState)
    })

  const submitScore = () =>
    run(async () => {
      if (teamId == null) throw new ApiError(400, '팀을 선택하세요.')
      await api.createScore(token, sessionId, {
        subject_type: 'team',
        subject_id: teamId,
        score: Number(score) || 0,
      })
      onScored()
    })

  const spin = () =>
    run(async () => {
      if (teams.length === 0) throw new ApiError(400, '팀이 없습니다.')
      const res = await api.rouletteSpin(token, sessionId, teams.map((t) => t.name), nonce)
      setSpinResult(res.selected)
      setNonce((n) => n + 1)
    })

  const nexts = NEXT_STATES[state]
  // 룰렛 시드는 in_progress 진입 시 생성됨 → 그 이후 상태에서만 스핀 가능
  const canSpin = ['in_progress', 'scoring', 'reward'].includes(state)

  return (
    <section className="op">
      <h3 className="section">🛠 운영자 패널</h3>

      <div className="op-state">
        현재 상태: <strong>{STATE_LABEL[state]}</strong> <span className="muted">({state})</span>
      </div>

      <div className="op-row">
        {nexts.length === 0 ? (
          <span className="muted">전이 가능한 다음 상태 없음 (종료)</span>
        ) : (
          nexts.map((to) => (
            <button key={to} className="op-btn" disabled={busy} onClick={() => transition(to)}>
              → {STATE_LABEL[to]}
            </button>
          ))
        )}
      </div>

      <div className="op-block">
        <div className="op-label">점수 기록</div>
        <div className="op-row">
          <select
            value={teamId ?? ''}
            onChange={(e) => setTeamId(e.target.value ? Number(e.target.value) : null)}
          >
            {teams.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <input
            className="op-score"
            type="number"
            value={score}
            onChange={(e) => setScore(e.target.value)}
          />
          <button className="op-btn" disabled={busy} onClick={submitScore}>
            기록
          </button>
        </div>
      </div>

      <div className="op-block">
        <div className="op-label">🎰 룰렛 (팀 대상)</div>
        <div className="op-row">
          <button className="op-btn" disabled={busy || !canSpin} onClick={spin}>
            스핀 (nonce {nonce})
          </button>
          {spinResult && <span className="op-result">당첨: {spinResult}</span>}
        </div>
        {!canSpin && <p className="muted">진행중(in_progress) 이후에 스핀 가능합니다.</p>}
      </div>

      {error && <p className="error">{error}</p>}
    </section>
  )
}
