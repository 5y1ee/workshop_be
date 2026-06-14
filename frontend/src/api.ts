const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export interface LoginResponse {
  access_token: string
  token_type: string
  user_id: number
  nickname: string
  role: string
  team_id: number | null
}

export interface Season {
  id: number
  name: string
  status: string
}

export interface TimetableEntry {
  id: number
  season_id: number
  game_id: number
  phase: string | null
  order_index: number
  label: string | null
  raffle_reward: number
}

export interface GameSession {
  id: number
  timetable_id: number
  state: string
  started_at: string | null
  ended_at: string | null
}

export interface Team {
  id: number
  season_id: number
  name: string
}

export interface ScoreSummaryItem {
  subject_type: string
  subject_id: number
  total_score: number
}

export type GameState = 'idle' | 'ready' | 'in_progress' | 'scoring' | 'reward' | 'done'

export interface TeamScore {
  team_id: number
  name: string
  total_score: number
}

export interface TeamMember {
  id: number
  nickname: string
  role: string
  point: number
  profile_image: string | null
}

export interface Reward {
  id: number
  name: string
  description: string | null
  total_count: number
  image_url: string | null
}

export interface GameResult {
  id: number
  session_id: number
  subject_type: string
  subject_id: number
}

export interface Game {
  id: number
  title: string
  description: string | null
  participant_type: string
  input_type: string
}

export interface RouletteSpinResult {
  session_id: number
  nonce: number
  options: string[]
  selected_index: number
  selected: string
  commitment: string
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(
  path: string,
  token: string | null,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      // 본문이 JSON 이 아니면 statusText 유지
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

export const api = {
  base: API_BASE,
  login: (username: string, password: string) =>
    request<LoginResponse>('/api/auth/login', null, {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  seasons: (token: string) => request<Season[]>('/api/seasons', token),
  timetable: (token: string, seasonId: number) =>
    request<TimetableEntry[]>(`/api/seasons/${seasonId}/timetable`, token),
  sessions: (token: string, timetableId: number) =>
    request<GameSession[]>(`/api/timetable/${timetableId}/sessions`, token),
  teams: (token: string, seasonId: number) =>
    request<Team[]>(`/api/seasons/${seasonId}/teams`, token),
  scoreSummary: (token: string, sessionId: number) =>
    request<ScoreSummaryItem[]>(`/api/sessions/${sessionId}/scores/summary`, token),

  // --- 포켓몬 UI 화면용 조회 ---
  seasonScoreboard: (token: string, seasonId: number) =>
    request<TeamScore[]>(`/api/seasons/${seasonId}/scoreboard`, token),
  teamMembers: (token: string, teamId: number) =>
    request<TeamMember[]>(`/api/teams/${teamId}/members`, token),
  rewards: (token: string) => request<Reward[]>('/api/rewards', token),
  results: (token: string, sessionId: number) =>
    request<GameResult[]>(`/api/sessions/${sessionId}/results`, token),
  games: (token: string) => request<Game[]>('/api/games', token),
  game: (token: string, gameId: number) => request<Game>(`/api/games/${gameId}`, token),

  // --- 운영자(admin) 전용 쓰기 ---
  createSession: (token: string, timetableId: number) =>
    request<GameSession>(`/api/timetable/${timetableId}/session`, token, { method: 'POST' }),
  transition: (token: string, sessionId: number, to: GameState) =>
    request<GameSession>(`/api/sessions/${sessionId}/transition`, token, {
      method: 'POST',
      body: JSON.stringify({ to }),
    }),
  createScore: (
    token: string,
    sessionId: number,
    body: { subject_type: 'team' | 'user'; subject_id: number; score: number; memo?: string },
  ) =>
    request<unknown>(`/api/sessions/${sessionId}/scores`, token, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  rouletteSpin: (token: string, sessionId: number, options: string[], nonce: number) =>
    request<RouletteSpinResult>(`/api/sessions/${sessionId}/roulette/spin`, token, {
      method: 'POST',
      body: JSON.stringify({ options, nonce }),
    }),
}

export function wsUrl(token: string): string {
  const base = API_BASE.replace(/^http/, 'ws')
  return `${base}/ws?token=${encodeURIComponent(token)}`
}
