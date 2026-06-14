import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, type Season } from './api'
import { useAuth } from './auth'

interface SeasonState {
  seasons: Season[]
  seasonId: number | null
  season: Season | null
  setSeasonId: (id: number) => void
  loading: boolean
}

const SeasonContext = createContext<SeasonState | null>(null)

/** 시즌 목록을 한 번 로드하고, 활성(active) 시즌을 기본 선택한다. */
export function SeasonProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth()
  const [seasons, setSeasons] = useState<Season[]>([])
  const [seasonId, setSeasonId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) return
    setLoading(true)
    api
      .seasons(token)
      .then((list) => {
        setSeasons(list)
        // active 우선, 없으면 가장 최근(id 큰) 시즌
        const active = list.find((s) => s.status === 'active')
        const fallback = list.length ? list[list.length - 1] : null
        setSeasonId((active ?? fallback)?.id ?? null)
      })
      .catch(() => setSeasons([]))
      .finally(() => setLoading(false))
  }, [token])

  const season = seasons.find((s) => s.id === seasonId) ?? null

  return (
    <SeasonContext.Provider value={{ seasons, seasonId, season, setSeasonId, loading }}>
      {children}
    </SeasonContext.Provider>
  )
}

export function useSeason(): SeasonState {
  const ctx = useContext(SeasonContext)
  if (!ctx) throw new Error('useSeason must be used within SeasonProvider')
  return ctx
}
