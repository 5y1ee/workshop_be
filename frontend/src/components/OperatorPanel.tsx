import { useEffect, useMemo, useState } from 'react'
import {
  api,
  ApiError,
  type GameState,
  type SeasonMembership,
  type Team,
  type UserProfile,
} from '../api'

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
  users: UserProfile[]
  memberships: SeasonMembership[]
  participantType: string
  onStateChange: (s: GameState) => void
  onScored: () => void
}

export default function OperatorPanel({
  token,
  sessionId,
  state,
  teams,
  users,
  memberships,
  participantType,
  onStateChange,
  onScored,
}: Props) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [teamId, setTeamId] = useState<number | null>(teams[0]?.id ?? null)
  const [userId, setUserId] = useState<number | null>(users[0]?.id ?? null)
  const [teamScore, setTeamScore] = useState('10')
  const [userScore, setUserScore] = useState('10')

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

  const userTeamId = (id: number | null) =>
    id == null ? null : memberships.find((m) => m.user_id === id)?.team_id ?? null

  const selectableUsers = useMemo(
    () => users.filter((u) => u.role === 'user' && userTeamId(u.id) != null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [memberships, users],
  )

  useEffect(() => {
    if ((teamId == null || !teams.some((t) => t.id === teamId)) && teams.length > 0) {
      setTeamId(teams[0].id)
    }
  }, [teamId, teams])

  useEffect(() => {
    if (
      (userId == null || !selectableUsers.some((u) => u.id === userId)) &&
      selectableUsers.length > 0
    ) {
      setUserId(selectableUsers[0].id)
    }
  }, [selectableUsers, userId])

  const submitTeamScore = () =>
    run(async () => {
      if (teamId == null) throw new ApiError(400, '팀을 선택하세요.')

      await api.createScore(token, sessionId, {
        subject_type: 'team',
        subject_id: teamId,
        score: Number(teamScore) || 0,
        memo: scoreMemo('team', teams.find((t) => t.id === teamId)?.name),
      })
      onScored()
    })

  const submitUserScore = () =>
    run(async () => {
      if (userId == null) throw new ApiError(400, '유저를 선택하세요.')
      await api.createScore(token, sessionId, {
        subject_type: 'user',
        subject_id: userId,
        score: Number(userScore) || 0,
        memo: scoreMemo('user', users.find((u) => u.id === userId)?.nickname),
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
        <div className="op-label">팀 점수 기록</div>
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
            value={teamScore}
            onChange={(e) => setTeamScore(e.target.value)}
          />
          <button className="op-btn" disabled={busy || teams.length === 0} onClick={submitTeamScore}>
            팀 점수 기록
          </button>
        </div>
      </div>

      <div className="op-block">
        <div className="op-label">개인 점수 기록</div>
        <div className="op-row">
          <select
            value={userId ?? ''}
            onChange={(e) => setUserId(e.target.value ? Number(e.target.value) : null)}
          >
            {selectableUsers.map((u) => {
              const memberTeam = teams.find((t) => t.id === userTeamId(u.id))
              const suffix = memberTeam ? ` · ${memberTeam.name}` : ''
              return (
                <option key={u.id} value={u.id}>
                  {u.nickname}{suffix}
                </option>
              )
            })}
          </select>
          <input
            className="op-score"
            type="number"
            value={userScore}
            onChange={(e) => setUserScore(e.target.value)}
          />
          <button
            className="op-btn"
            disabled={busy || selectableUsers.length === 0}
            onClick={submitUserScore}
          >
            개인 점수 기록
          </button>
        </div>
        <p className="muted">현재 게임 참여자 유형: {participantTypeLabel(participantType)}</p>
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

function participantTypeLabel(value: string) {
  if (value === 'team_vs') return '팀 점수'
  if (value === 'individual') return '개인 점수'
  if (value === 'representative') return '대표 참여 · 팀 점수'
  if (value === 'team_internal') return '팀 내부 개인 점수'
  return '점수'
}

function scoreMemo(
  subjectType: 'team' | 'user',
  name?: string,
) {
  if (!name) return undefined
  return subjectType === 'team' ? `팀 ${name}` : `개인 ${name}`
}
