import { useCallback, useEffect, useState } from 'react'
import {
  api,
  type GameSession,
  type ScoreSummaryItem,
  type Season,
  type Team,
  type TimetableEntry,
} from '../api'
import { useAuth } from '../auth'
import { useWebSocket, type WsEvent } from '../useWebSocket'

const LOG_LIMIT = 20

export default function ScoreboardPage() {
  const { token, user, logout } = useAuth()
  const t = token as string

  const [seasons, setSeasons] = useState<Season[]>([])
  const [seasonId, setSeasonId] = useState<number | null>(null)
  const [entries, setEntries] = useState<TimetableEntry[]>([])
  const [entryId, setEntryId] = useState<number | null>(null)
  const [sessions, setSessions] = useState<GameSession[]>([])
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [teams, setTeams] = useState<Team[]>([])
  const [summary, setSummary] = useState<ScoreSummaryItem[]>([])
  const [log, setLog] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  // 시즌 목록
  useEffect(() => {
    api.seasons(t).then(setSeasons).catch((e) => setError(String(e)))
  }, [t])

  // 시즌 선택 → 타임테이블 + 팀
  useEffect(() => {
    if (seasonId == null) return
    setEntryId(null)
    setEntries([])
    setSessions([])
    setSessionId(null)
    api.timetable(t, seasonId).then(setEntries).catch(() => setEntries([]))
    api.teams(t, seasonId).then(setTeams).catch(() => setTeams([]))
  }, [t, seasonId])

  // 타임테이블 선택 → 세션
  useEffect(() => {
    if (entryId == null) return
    setSessionId(null)
    setSessions([])
    api.sessions(t, entryId).then(setSessions).catch(() => setSessions([]))
  }, [t, entryId])

  const refreshSummary = useCallback(() => {
    if (sessionId == null) {
      setSummary([])
      return
    }
    api.scoreSummary(t, sessionId).then(setSummary).catch(() => setSummary([]))
  }, [t, sessionId])

  useEffect(() => {
    refreshSummary()
  }, [refreshSummary])

  const teamName = (id: number) => teams.find((x) => x.id === id)?.name ?? `팀 #${id}`
  const subjectLabel = (s: ScoreSummaryItem) =>
    s.subject_type === 'team' ? teamName(s.subject_id) : `유저 #${s.subject_id}`

  const pushLog = (text: string) =>
    setLog((prev) => [`${new Date().toLocaleTimeString()} · ${text}`, ...prev].slice(0, LOG_LIMIT))

  // 실시간 이벤트
  const onEvent = useCallback(
    (e: WsEvent) => {
      const sid = e.session_id as number | undefined
      switch (e.type) {
        case 'score_recorded':
          pushLog(`점수 기록 (세션 #${sid})`)
          if (sid === sessionId) refreshSummary()
          break
        case 'result_recorded':
          pushLog(`결과 기록 (세션 #${sid})`)
          break
        case 'session_state_changed':
          pushLog(`상태 → ${e.state} (세션 #${sid})`)
          break
        case 'roulette_result':
          pushLog(`🎰 룰렛 → ${e.selected} (세션 #${sid})`)
          break
        default:
          break
      }
    },
    [sessionId, refreshSummary],
  )
  const { connected } = useWebSocket(token, onEvent)

  return (
    <div className="page">
      <header className="topbar">
        <span className="greet">👋 {user?.nickname}</span>
        <span className={connected ? 'live on' : 'live off'}>
          {connected ? '● LIVE' : '○ 연결 끊김'}
        </span>
        <button className="link" onClick={logout}>
          로그아웃
        </button>
      </header>

      {error && <p className="error">{error}</p>}

      <div className="selectors">
        <select
          value={seasonId ?? ''}
          onChange={(e) => setSeasonId(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">시즌 선택</option>
          {seasons.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} ({s.status})
            </option>
          ))}
        </select>

        <select
          value={entryId ?? ''}
          onChange={(e) => setEntryId(e.target.value ? Number(e.target.value) : null)}
          disabled={entries.length === 0}
        >
          <option value="">게임(타임테이블) 선택</option>
          {entries.map((en) => (
            <option key={en.id} value={en.id}>
              {en.order_index}. {en.label ?? `게임 #${en.game_id}`}
            </option>
          ))}
        </select>

        <select
          value={sessionId ?? ''}
          onChange={(e) => setSessionId(e.target.value ? Number(e.target.value) : null)}
          disabled={sessions.length === 0}
        >
          <option value="">세션 선택</option>
          {sessions.map((se) => (
            <option key={se.id} value={se.id}>
              세션 #{se.id} — {se.state}
            </option>
          ))}
        </select>
      </div>

      <h2 className="section">🏆 스코어보드</h2>
      {sessionId == null ? (
        <p className="muted">시즌 → 게임 → 세션을 선택하세요.</p>
      ) : summary.length === 0 ? (
        <p className="muted">아직 기록된 점수가 없습니다.</p>
      ) : (
        <ol className="board">
          {summary.map((s, i) => (
            <li key={`${s.subject_type}-${s.subject_id}`} className={`row rank-${i + 1}`}>
              <span className="rank">{i + 1}</span>
              <span className="name">{subjectLabel(s)}</span>
              <span className="score">{s.total_score}</span>
            </li>
          ))}
        </ol>
      )}

      <h3 className="section">📡 실시간 이벤트</h3>
      <ul className="log">
        {log.length === 0 ? (
          <li className="muted">이벤트 대기 중…</li>
        ) : (
          log.map((line, i) => <li key={i}>{line}</li>)
        )}
      </ul>
    </div>
  )
}
