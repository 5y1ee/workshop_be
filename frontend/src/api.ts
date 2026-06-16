const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export interface LoginResponse {
  access_token: string
  token_type: string
  user_id: number
  nickname: string
  role: string
  team_id: number | null
}

export interface UserProfile {
  id: number
  username: string
  nickname: string
  role: string
  point: number
  profile_image: string | null
}

/** 시즌 내 유저-팀 배정 현황 */
export interface SeasonMembership {
  user_id: number
  team_id: number
}

/** 선택 시즌에서의 내 팀 (없으면 team_id=null) */
export interface MyTeam {
  team_id: number | null
  name: string | null
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
  subject_name: string | null
  total_score: number
}

export interface ScoreLog {
  id: number
  session_id: number
  subject_type: string
  subject_id: number
  chat_log_id: number | null
  score: number
  memo: string | null
  created_by: number
  created_at: string
  updated_at: string | null
}

export type GameState = 'idle' | 'ready' | 'in_progress' | 'scoring' | 'reward' | 'done'

export interface TeamScore {
  team_id: number
  name: string
  total_score: number
}

export interface UserScore {
  user_id: number
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
  season_id: number
  name: string
  description: string | null
  total_count: number
  image_url: string | null
  win_rate: number
  is_revealed: boolean
}

export interface RewardWithClaims extends Reward {
  claimed_count: number
  remaining_count: number
  my_claimed: boolean
}

export interface RewardClaimDetail {
  id: number
  reward_id: number
  user_id: number
  nickname: string
  claimed_at: string
}

export interface GachaPullResponse {
  is_win: boolean
  reward: Reward | null
  remaining_point: number
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

export type RoundStatus = 'waiting' | 'open' | 'closed'
export type TapMode = 'count' | 'speed' | 'timing'

export interface GameRound {
  id: number
  session_id: number
  order_index: number
  status: RoundStatus
  prompt: string | null
  media_url: string | null
  options: string[] | null
  opened_at: string | null
  closed_at: string | null
  tap_mode: TapMode | null
  duration: number | null
  target_time: number | null
  signal_at: string | null
  created_at: string
  updated_at: string | null
}

export interface TapResult {
  user_id: number
  nickname: string
  team_id: number | null
  team_name: string | null
  value: number
  rank: number
}

export interface RoundReveal {
  round_id: number
  correct_answer: string | null
  total_submissions: number
  distribution: Record<string, number>
}

export interface ChatLog {
  id: number
  session_id: number
  round_id: number | null
  user_id: number
  nickname: string
  team_id: number | null
  team_name: string | null
  message: string
  is_correct: boolean
  server_time: string
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
  // 204 No Content 등 본문 없는 응답
  if (res.status === 204 || res.headers.get('content-length') === '0') {
    return undefined as T
  }
  return (await res.json()) as T
}

export const api = {
  base: API_BASE,
  login: (username: string, password: string) =>
    request<LoginResponse>('/api/auth/login', null, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username, password }).toString(),
    }),
  me: (token: string) => request<UserProfile>('/api/auth/me', token),
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
  seasonUserScoreboard: (token: string, seasonId: number) =>
    request<UserScore[]>(`/api/seasons/${seasonId}/user-scoreboard`, token),
  teamMembers: (token: string, teamId: number) =>
    request<TeamMember[]>(`/api/teams/${teamId}/members`, token),
  myTeam: (token: string, seasonId: number) =>
    request<MyTeam>(`/api/seasons/${seasonId}/my-team`, token),
  seasonMembers: (token: string, seasonId: number) =>
    request<SeasonMembership[]>(`/api/seasons/${seasonId}/members`, token),
  rewards: (token: string, seasonId: number) =>
    request<RewardWithClaims[]>(`/api/seasons/${seasonId}/rewards`, token),
  gachaPull: (token: string, seasonId: number) =>
    request<GachaPullResponse>(`/api/gacha/pull?season_id=${seasonId}`, token, {
      method: 'POST',
    }),
  results: (token: string, sessionId: number) =>
    request<GameResult[]>(`/api/sessions/${sessionId}/results`, token),
  games: (token: string) => request<Game[]>('/api/games', token),
  game: (token: string, gameId: number) => request<Game>(`/api/games/${gameId}`, token),
  createGame: (
    token: string,
    body: { title: string; description?: string | null; participant_type: string; input_type: string },
  ) =>
    request<Game>('/api/games', token, { method: 'POST', body: JSON.stringify(body) }),
  createTimetable: (
    token: string,
    seasonId: number,
    body: { game_id: number; order_index: number; label?: string | null },
  ) =>
    request<TimetableEntry>(`/api/seasons/${seasonId}/timetable`, token, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateTimetable: (
    token: string,
    entryId: number,
    body: { game_id?: number; order_index?: number; phase?: string | null; label?: string | null; raffle_reward?: number },
  ) =>
    request<TimetableEntry>(`/api/timetable/${entryId}`, token, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  deleteTimetable: (token: string, entryId: number) =>
    request<void>(`/api/timetable/${entryId}`, token, { method: 'DELETE' }),

  // --- 운영자(admin) 전용 쓰기 ---
  createSession: (token: string, timetableId: number) =>
    request<GameSession>(`/api/timetable/${timetableId}/session`, token, { method: 'POST' }),
  session: (token: string, sessionId: number) =>
    request<GameSession>(`/api/sessions/${sessionId}`, token),
  transition: (token: string, sessionId: number, to: GameState) =>
    request<GameSession>(`/api/sessions/${sessionId}/transition`, token, {
      method: 'POST',
      body: JSON.stringify({ to }),
    }),
  createScore: (
    token: string,
    sessionId: number,
    body: {
      subject_type: 'team' | 'user'
      subject_id: number
      score: number
      memo?: string
      chat_log_id?: number | null
    },
  ) =>
    request<ScoreLog>(`/api/sessions/${sessionId}/scores`, token, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  scores: (token: string, sessionId: number) =>
    request<ScoreLog[]>(`/api/sessions/${sessionId}/scores`, token),
  rouletteSpin: (token: string, sessionId: number, options: string[], nonce: number) =>
    request<RouletteSpinResult>(`/api/sessions/${sessionId}/roulette/spin`, token, {
      method: 'POST',
      body: JSON.stringify({ options, nonce }),
    }),

  // --- 게임 라운드(세션 내부 진행도) ---
  rounds: (token: string, sessionId: number) =>
    request<GameRound[]>(`/api/sessions/${sessionId}/rounds`, token),
  currentRound: (token: string, sessionId: number) =>
    request<GameRound>(`/api/sessions/${sessionId}/rounds/current`, token),
  createRound: (
    token: string,
    sessionId: number,
    body: {
      order_index: number
      prompt?: string | null
      media_url?: string | null
      options?: string[] | null
      correct_answer?: string | null
      tap_mode?: TapMode | null
      duration?: number | null
      target_time?: number | null
    },
  ) =>
    request<GameRound>(`/api/sessions/${sessionId}/rounds`, token, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  openRound: (token: string, roundId: number) =>
    request<GameRound>(`/api/rounds/${roundId}/open`, token, { method: 'POST' }),
  closeRound: (token: string, roundId: number) =>
    request<RoundReveal>(`/api/rounds/${roundId}/close`, token, { method: 'POST' }),
  revealRound: (token: string, roundId: number) =>
    request<RoundReveal>(`/api/rounds/${roundId}/reveal`, token),
  sendTapSignal: (token: string, roundId: number) =>
    request<{ status: string }>(`/api/rounds/${roundId}/signal`, token, { method: 'POST' }),
  chatLogs: (token: string, sessionId: number, roundId?: number | null) => {
    const qs = roundId == null ? '' : `?round_id=${roundId}`
    return request<ChatLog[]>(`/api/sessions/${sessionId}/chat-logs${qs}`, token)
  },

  // --- 운영자(admin) 관리: 시즌 / 팀 / 유저 ---
  createSeason: (token: string, name: string) =>
    request<Season>('/api/seasons', token, {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
  updateSeason: (
    token: string,
    seasonId: number,
    body: { name?: string; status?: 'preparing' | 'active' | 'done' },
  ) =>
    request<Season>(`/api/seasons/${seasonId}`, token, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  createTeam: (token: string, seasonId: number, name: string) =>
    request<Team>(`/api/seasons/${seasonId}/teams`, token, {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
  updateTeam: (token: string, teamId: number, name: string) =>
    request<Team>(`/api/teams/${teamId}`, token, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),
  deleteSeason: (token: string, seasonId: number) =>
    request<void>(`/api/seasons/${seasonId}`, token, { method: 'DELETE' }),
  deleteTeam: (token: string, teamId: number) =>
    request<void>(`/api/teams/${teamId}`, token, { method: 'DELETE' }),
  users: (token: string, params?: { role?: string }) => {
    const q = new URLSearchParams()
    if (params?.role) q.set('role', params.role)
    const qs = q.toString()
    return request<UserProfile[]>(`/api/users${qs ? `?${qs}` : ''}`, token)
  },
  createUser: (
    token: string,
    body: { username: string; password: string; nickname: string; role: 'admin' | 'user' },
  ) =>
    request<UserProfile>('/api/users', token, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateUser: (
    token: string,
    userId: number,
    body: { nickname?: string; role?: 'admin' | 'user' },
  ) =>
    request<UserProfile>(`/api/users/${userId}`, token, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  // --- 시즌별 팀 배정 (멤버십) ---
  assignMember: (token: string, seasonId: number, teamId: number, userId: number) =>
    request<SeasonMembership>(
      `/api/seasons/${seasonId}/teams/${teamId}/members`,
      token,
      { method: 'POST', body: JSON.stringify({ user_id: userId }) },
    ),
  unassignMember: (token: string, seasonId: number, userId: number) =>
    request<void>(`/api/seasons/${seasonId}/members/${userId}`, token, {
      method: 'DELETE',
    }),

  // --- 시즌별 리워드 도감 관리 ---
  createReward: (
    token: string,
    seasonId: number,
    body: { name: string; description?: string | null; total_count: number; image_url?: string | null; win_rate_pct?: number },
  ) =>
    request<Reward>(`/api/seasons/${seasonId}/rewards`, token, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateReward: (
    token: string,
    rewardId: number,
    body: { name?: string; total_count?: number; image_url?: string | null; win_rate_pct?: number },
  ) =>
    request<Reward>(`/api/rewards/${rewardId}`, token, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  deleteReward: (token: string, rewardId: number) =>
    request<void>(`/api/rewards/${rewardId}`, token, { method: 'DELETE' }),
  rewardClaims: (token: string, rewardId: number) =>
    request<RewardClaimDetail[]>(`/api/rewards/${rewardId}/claims`, token),
}

export function wsUrl(token: string): string {
  const base = API_BASE.replace(/^http/, 'ws')
  return `${base}/ws?token=${encodeURIComponent(token)}`
}

/** API/DB 에 저장된 상대 경로를 브라우저에서 쓸 수 있는 URL 로 변환한다. */
export function resolveAssetUrl(path: string | null | undefined): string | null {
  if (!path) return null
  if (path.startsWith('http://') || path.startsWith('https://')) return path
  if (path.startsWith('/')) return `${API_BASE}${path}`
  return `${API_BASE}/${path}`
}
