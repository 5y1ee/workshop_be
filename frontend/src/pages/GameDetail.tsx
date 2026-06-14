import { useCallback, useEffect, useState } from 'react'
import {
  api,
  type Game,
  type GameResult,
  type GameSession,
  type GameState,
  type ScoreSummaryItem,
  type Team,
  type TimetableEntry,
} from '../api'
import { useAuth } from '../auth'
import { useLive } from '../live'
import OperatorPanel from '../components/OperatorPanel'

interface Props {
  entry: TimetableEntry
  session: GameSession | null
  game: Game | null
  seasonId: number
  onBack: () => void
  onSessionChanged: () => void
}

const STATE_LABEL: Record<GameState, string> = {
  idle: '대기',
  ready: '준비',
  in_progress: '진행중',
  scoring: '채점중',
  reward: '보상',
  done: '종료',
}

export default function GameDetail({
  entry,
  session,
  game,
  seasonId,
  onBack,
  onSessionChanged,
}: Props) {
  const { token, user } = useAuth()
  const t = token as string
  const { lastEvent } = useLive()
  const isAdmin = user?.role === 'admin'

  const [sessionId, setSessionId] = useState<number | null>(session?.id ?? null)
  const [state, setState] = useState<GameState | null>((session?.state as GameState) ?? null)
  const [summary, setSummary] = useState<ScoreSummaryItem[]>([])
  const [results, setResults] = useState<GameResult[]>([])
  const [teams, setTeams] = useState<Team[]>([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.teams(t, seasonId).then(setTeams).catch(() => setTeams([]))
  }, [t, seasonId])

  const teamName = (id: number) => teams.find((x) => x.id === id)?.name ?? `팀 #${id}`
  const subjectLabel = (type: string, id: number) =>
    type === 'team' ? teamName(id) : `유저 #${id}`

  const refresh = useCallback(() => {
    if (sessionId == null) {
      setSummary([])
      setResults([])
      return
    }
    api.scoreSummary(t, sessionId).then(setSummary).catch(() => setSummary([]))
    api.results(t, sessionId).then(setResults).catch(() => setResults([]))
  }, [t, sessionId])

  useEffect(refresh, [refresh])
  useEffect(() => {
    const sid = lastEvent?.session_id as number | undefined
    if (sid === sessionId) refresh()
  }, [lastEvent, sessionId, refresh])

  const createSession = async () => {
    setBusy(true)
    try {
      const s = await api.createSession(t, entry.id)
      setSessionId(s.id)
      setState(s.state as GameState)
      onSessionChanged()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page">
      <button className="back" onClick={onBack}>
        ← 진행 목록
      </button>

      <h2 className="detail-title">
        {entry.order_index}. {entry.label ?? game?.title ?? `게임 #${entry.game_id}`}
      </h2>
      {game?.description && <p className="muted">{game.description}</p>}
      <div className="detail-meta">
        {game && (
          <span className="chip">
            {game.participant_type} · {game.input_type}
          </span>
        )}
        {state && <span className="chip state">{STATE_LABEL[state]}</span>}
      </div>

      {sessionId == null ? (
        <div className="card" style={{ marginTop: 14 }}>
          <p className="muted">아직 세션이 시작되지 않았습니다.</p>
          {isAdmin && (
            <button className="op-btn" disabled={busy} onClick={createSession}>
              세션 생성
            </button>
          )}
        </div>
      ) : (
        <>
          <h3 className="sec-title">🏆 스코어보드</h3>
          {summary.length === 0 ? (
            <p className="muted">아직 기록된 점수가 없습니다.</p>
          ) : (
            <ol className="board">
              {summary.map((s, i) => (
                <li key={`${s.subject_type}-${s.subject_id}`} className={`row rank-${i + 1}`}>
                  <span className="rank">{i + 1}</span>
                  <span className="name">{subjectLabel(s.subject_type, s.subject_id)}</span>
                  <span className="score">{s.total_score}</span>
                </li>
              ))}
            </ol>
          )}

          {results.length > 0 && (
            <>
              <h3 className="sec-title">🏅 최종 결과</h3>
              <div className="card">
                {results.map((r) => (
                  <div key={r.id}>🎉 {subjectLabel(r.subject_type, r.subject_id)} 우승</div>
                ))}
              </div>
            </>
          )}

          {isAdmin && state && (
            <OperatorPanel
              key={sessionId}
              token={t}
              sessionId={sessionId}
              state={state}
              teams={teams}
              onStateChange={setState}
              onScored={refresh}
            />
          )}
        </>
      )}
    </div>
  )
}
