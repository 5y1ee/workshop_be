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

const MARKER_SIZE = 'clamp(118px, 38vw, 210px)'
const MIN_MAIN_HEIGHT_VH = 100
const MAIN_HEIGHT_BASE_VH = 32
const MAIN_HEIGHT_PER_GAME_VH = 13
const ROUTE_TOP_PCT = 12
const ROUTE_BOTTOM_PCT = 88

const GAME_MARKERS_BY_TITLE: Record<string, { image: string }> = {
  '몸으로 말해요': { image: 'charades.png' },
  '퀴즈 대결': { image: 'quiz-battle.png' },
  '노래 맞추기': { image: 'song-quiz.png' },
  보물찾기: { image: 'treasure-hunt.png' },
  '릴레이 게임': { image: 'relay-game.png' },
  '철인 3종': { image: 'triathlon.png' },
  '신발 던지기': { image: 'shoe-throw.png' },
  좀비게임: { image: 'zombie-game.png' },
  '팀 오프라인 게임': { image: 'offline-game.png' },
  '개인 오프라인 게임': { image: 'offline-game.png' },
}

const FALLBACK_MARKERS = [
  ...new Map(Object.values(GAME_MARKERS_BY_TITLE).map((m) => [m.image, m])).values(),
]
const MARKER_X_PATTERN = ['55%', '25%', '72%', '38%', '78%', '24%', '73%', '25%']

function markerTop(index: number, count: number): string {
  if (count <= 1) return '50%'
  const span = ROUTE_BOTTOM_PCT - ROUTE_TOP_PCT
  return `${ROUTE_BOTTOM_PCT - (span * index) / (count - 1)}%`
}

function cleanGameLabel(label: string): string {
  return label.replace(/^\s*\d+\.\s*/, '')
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
    if (
      lastEvent?.type === 'session_created' ||
      lastEvent?.type === 'session_state_changed' ||
      (lastEvent?.type === 'timetable_changed' && lastEvent.season_id === seasonId)
    ) {
      loadEntries()
    }
  }, [lastEvent, loadEntries])

  const title = (e: TimetableEntry) =>
    cleanGameLabel(e.label ?? games[e.game_id]?.title ?? `게임 #${e.game_id}`)
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

  const displayEntries = entries.filter((e) => games[e.game_id]?.input_type !== 'tap')
  const mainHeight = `${Math.max(
    MIN_MAIN_HEIGHT_VH,
    MAIN_HEIGHT_BASE_VH + displayEntries.length * MAIN_HEIGHT_PER_GAME_VH,
  )}vh`

  return (
    <div className="page main" style={{ '--main-map-height': mainHeight } as CSSProperties}>
      {displayEntries.map((e, visibleIndex) => {
        const game = games[e.game_id]
        const marker =
          (game ? GAME_MARKERS_BY_TITLE[game.title] : null) ??
          FALLBACK_MARKERS[visibleIndex % FALLBACK_MARKERS.length]
        if (!marker) return null
        const s = sessions[e.id]
        const st = (s?.state as GameState) ?? null
        const done = st === 'done'
        const live = st === 'in_progress' || st === 'scoring' || st === 'reward'
        const isMainVisible = e.main_visible !== false
        const label = title(e)
        return (
          <button
            key={e.id}
            className={`gym-marker${done ? ' done' : ''}${live ? ' live' : ''}${isMainVisible ? '' : ' dimmed'}`}
            style={{
              left: MARKER_X_PATTERN[visibleIndex % MARKER_X_PATTERN.length],
              top: markerTop(visibleIndex, displayEntries.length),
              '--marker-size': MARKER_SIZE,
            } as CSSProperties}
            onClick={() => {
              if (isMainVisible) setSelected(e)
            }}
            aria-label={label}
            aria-disabled={!isMainVisible}
            tabIndex={isMainVisible ? 0 : -1}
          >
            <img src={`/images/${marker.image}`} alt="" />
            {isMainVisible && <span className="gym-title">{label}</span>}
          </button>
        )
      })}
    </div>
  )
}
