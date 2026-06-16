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
  // const doneCount = Object.values(sessions).filter((s) => s?.state === 'done').length

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

  // order_index 1(맨 아래) → 9(맨 위) 순서로 섬 위치 정의 (progress-bg.png 기준)
  const GYM_POSITIONS: { x: string; y: string }[] = [
    { x: '50%', y: '91%' }, // 1 - 몸으로 말해요 (하단 중앙)
    { x: '23%', y: '76%' }, // 2 - 퀴즈 대결 (좌)
    { x: '65%', y: '66%' }, // 3 - 노래 맞추기 (우)
    { x: '25%', y: '56%' }, // 4 - 보물찾기 (좌)
    { x: '63%', y: '46%' }, // 5 - 릴레이 게임 (우)
    { x: '23%', y: '36%' }, // 6 - 철인 3종 (좌)
    { x: '66%', y: '25%' }, // 7 - 신발 던지기 (우)
    { x: '21%', y: '16%' }, // 8 - 좀비게임 (좌)
    { x: '50%', y: '6%'  }, // 9 - 버튼 챌린지 (상단 중앙)
  ]

  return (
    <div className="page main">
      {entries.map((e) => {
        const pos = GYM_POSITIONS[e.order_index - 1]
        if (!pos) return null
        const s = sessions[e.id]
        const st = (s?.state as GameState) ?? null
        const done = st === 'done'
        const live = st === 'in_progress' || st === 'scoring' || st === 'reward'
        return (
          <div
            key={e.id}
            className={`gym-marker${done ? ' done' : ''}${live ? ' live' : ''}`}
            style={{ left: pos.x, top: pos.y }}
            onClick={() => setSelected(e)}
          >
            <span className="gym-title">{games[e.game_id]?.title ?? title(e)}</span>
          </div>
        )
      })}
    </div>
  )
}
