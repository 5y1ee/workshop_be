import { useCallback, useEffect, useState, type CSSProperties } from 'react'
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

const MARKER_SIZE = '40vw'

const GAME_MARKERS: Record<number, { x: string; y: string; image: string }> = {
  1: { x: '55%', y: '89%', image: 'charades.png' },
  2: { x: '25%', y: '78%', image: 'quiz-battle.png' },
  3: { x: '72%', y: '70%', image: 'song-quiz.png' },
  4: { x: '38%', y: '60%', image: 'treasure-hunt.png' },
  5: { x: '78%', y: '47%', image: 'relay-game.png' },
  6: { x: '24%', y: '44%', image: 'triathlon.png' },
  7: { x: '73%', y: '27%', image: 'shoe-throw.png' },
  8: { x: '25%', y: '25%', image: 'zombie-game.png' },
  9: { x: '51%', y: '10%', image: 'button-challenge.png' },
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

  return (
    <div className="page main">
      {entries.map((e) => {
        const marker = GAME_MARKERS[e.order_index]
        if (!marker) return null
        const s = sessions[e.id]
        const st = (s?.state as GameState) ?? null
        const done = st === 'done'
        const live = st === 'in_progress' || st === 'scoring' || st === 'reward'
        const label = games[e.game_id]?.title ?? title(e)
        return (
          <button
            key={e.id}
            className={`gym-marker${done ? ' done' : ''}${live ? ' live' : ''}`}
            style={{ left: marker.x, top: marker.y, '--marker-size': MARKER_SIZE } as CSSProperties}
            onClick={() => setSelected(e)}
            aria-label={label}
          >
            <img src={`/images/${marker.image}`} alt="" />
            <span className="gym-title">{label}</span>
          </button>
        )
      })}
    </div>
  )
}
