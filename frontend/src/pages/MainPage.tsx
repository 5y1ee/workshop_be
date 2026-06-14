import { useCallback, useEffect, useState } from 'react'
import {
  api,
  type Game,
  type GameSession,
  type GameState,
  type TimetableEntry,
} from '../api'
import { useAuth } from '../auth'
import { useSeason } from '../season'
import { useLive } from '../live'
import GameDetail from './GameDetail'

const STATE_PILL: Record<GameState, { cls: string; label: string }> = {
  idle: { cls: 's-idle', label: '대기' },
  ready: { cls: 's-idle', label: '준비' },
  in_progress: { cls: 's-live', label: '진행중' },
  scoring: { cls: 's-live', label: '채점중' },
  reward: { cls: 's-live', label: '보상' },
  done: { cls: 's-done', label: '종료' },
}

export default function MainPage() {
  const { token } = useAuth()
  const t = token as string
  const { seasonId } = useSeason()
  const { lastEvent } = useLive()

  const [entries, setEntries] = useState<TimetableEntry[]>([])
  const [games, setGames] = useState<Record<number, Game>>({})
  const [sessions, setSessions] = useState<Record<number, GameSession | null>>({})
  const [selected, setSelected] = useState<TimetableEntry | null>(null)

  // 게임 목록 (id → 제목)
  useEffect(() => {
    api
      .games(t)
      .then((list) => setGames(Object.fromEntries(list.map((g) => [g.id, g]))))
      .catch(() => setGames({}))
  }, [t])

  // 타임테이블 + 각 항목의 최신 세션
  const loadEntries = useCallback(() => {
    if (seasonId == null) return
    api
      .timetable(t, seasonId)
      .then(async (list) => {
        const sorted = [...list].sort((a, b) => a.order_index - b.order_index)
        setEntries(sorted)
        const pairs = await Promise.all(
          sorted.map(async (e) => {
            const ss = await api.sessions(t, e.id).catch(() => [])
            return [e.id, ss.length ? ss[ss.length - 1] : null] as const
          }),
        )
        setSessions(Object.fromEntries(pairs))
      })
      .catch(() => setEntries([]))
  }, [t, seasonId])

  useEffect(loadEntries, [loadEntries])
  useEffect(() => {
    if (lastEvent?.type === 'session_state_changed') loadEntries()
  }, [lastEvent, loadEntries])

  const title = (e: TimetableEntry) => e.label ?? games[e.game_id]?.title ?? `게임 #${e.game_id}`
  const doneCount = Object.values(sessions).filter((s) => s?.state === 'done').length

  if (selected) {
    return (
      <GameDetail
        entry={selected}
        session={sessions[selected.id] ?? null}
        game={games[selected.game_id] ?? null}
        seasonId={seasonId as number}
        onBack={() => setSelected(null)}
        onSessionChanged={loadEntries}
      />
    )
  }

  return (
    <div className="page">
      <div className="progress">
        시즌 진행도 {doneCount} / {entries.length} 게임
        <div className="bar">
          <i style={{ width: entries.length ? `${(doneCount / entries.length) * 100}%` : '0%' }} />
        </div>
      </div>

      {entries.length === 0 ? (
        <p className="muted">등록된 게임(타임테이블)이 없습니다.</p>
      ) : (
        <div className="route">
          {entries.map((e) => {
            const s = sessions[e.id]
            const st = (s?.state as GameState) ?? null
            const pill = st ? STATE_PILL[st] : { cls: 's-idle', label: '세션없음' }
            const live = st === 'in_progress' || st === 'scoring' || st === 'reward'
            const done = st === 'done'
            return (
              <div
                key={e.id}
                className={`stop${done ? ' done' : ''}${live ? ' live' : ''}`}
                onClick={() => setSelected(e)}
              >
                <div className="dot">{done ? '✓' : live ? '⚡' : ''}</div>
                <div className="game-card">
                  <span className={`state-pill ${pill.cls}`}>{pill.label}</span>
                  <div className="gname">
                    {e.order_index}. {title(e)}
                  </div>
                  <div className="gmeta">탭하면 상세 · 점수/결과 히스토리</div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
