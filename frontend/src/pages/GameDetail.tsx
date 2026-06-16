import { useCallback, useEffect, useState } from 'react'
import {
  api,
  type Game,
  type GameResult,
  type GameRound,
  type GameSession,
  type GameState,
  type ScoreSummaryItem,
  type SeasonMembership,
  type Team,
  type TimetableEntry,
  type UserProfile,
} from '../api'
import { useAuth } from '../auth'
import { useLive } from '../live'
import OperatorPanel from '../components/OperatorPanel'
import RoundOperator from '../components/RoundOperator'
import ChatPanel from '../components/ChatPanel'
import ButtonPanel from '../components/ButtonPanel'
import ChatJudgePanel from '../components/ChatJudgePanel'
import TapPanel from '../components/TapPanel'
import TapOperatorPanel from '../components/TapOperatorPanel'

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
  const { lastEvent, send, connected } = useLive()
  const isAdmin = user?.role === 'admin'

  const [sessionId, setSessionId] = useState<number | null>(session?.id ?? null)
  const [state, setState] = useState<GameState | null>((session?.state as GameState) ?? null)
  const [summary, setSummary] = useState<ScoreSummaryItem[]>([])
  const [results, setResults] = useState<GameResult[]>([])
  const [teams, setTeams] = useState<Team[]>([])
  const [users, setUsers] = useState<UserProfile[]>([])
  const [memberships, setMemberships] = useState<SeasonMembership[]>([])
  const [rounds, setRounds] = useState<GameRound[]>([])
  const [busy, setBusy] = useState(false)

  const inputType = game?.input_type ?? ''
  const isChat = inputType === 'chat'
  const isButton = inputType === 'button' || inputType === 'vote'
  const isTap = inputType === 'tap'
  const currentRound = rounds.find((r) => r.status === 'open') ?? null

  useEffect(() => {
    api.teams(t, seasonId).then(setTeams).catch(() => setTeams([]))
  }, [t, seasonId])

  useEffect(() => {
    if (!isAdmin) {
      setUsers([])
      setMemberships([])
      return
    }
    api.users(t, { role: 'user' }).then(setUsers).catch(() => setUsers([]))
    api.seasonMembers(t, seasonId).then(setMemberships).catch(() => setMemberships([]))
  }, [isAdmin, t, seasonId])

  const teamName = (id: number) => teams.find((x) => x.id === id)?.name ?? `팀 #${id}`
  const subjectLabel = (type: string, id: number, name?: string | null) => {
    if (name) return name
    return type === 'team' ? teamName(id) : `유저 #${id}`
  }

  const refresh = useCallback(() => {
    if (sessionId == null) {
      setSummary([])
      setResults([])
      setRounds([])
      return
    }
    api.scoreSummary(t, sessionId).then(setSummary).catch(() => setSummary([]))
    api.results(t, sessionId).then(setResults).catch(() => setResults([]))
    api.rounds(t, sessionId).then(setRounds).catch(() => setRounds([]))
  }, [t, sessionId])

  useEffect(refresh, [refresh])

  // 구조가 바뀌는 이벤트에서만 갱신 (채팅/제출 카운트 같은 고빈도 이벤트는 제외)
  useEffect(() => {
    const sid = lastEvent?.session_id as number | undefined
    if (sid !== sessionId || !lastEvent) return

    // session_state_changed: 이벤트 페이로드의 state를 즉시 반영 (운영자 외 다른 클라이언트 동기화)
    if (lastEvent.type === 'session_state_changed' && typeof lastEvent.state === 'string') {
      setState(lastEvent.state as GameState)
    }

    const structural = [
      'round_started',
      'round_revealed',
      'session_state_changed',
      'score_recorded',
      'result_recorded',
    ]
    if (structural.includes(lastEvent.type)) {
      refresh()
    }
  }, [lastEvent, sessionId, refresh])

  // 게임 상세 진입 = 해당 세션 실시간 방에 합류
  useEffect(() => {
    if (sessionId == null || !connected) return
    send({ type: 'join_session', session_id: sessionId })
    return () => {
      send({ type: 'leave_session', session_id: sessionId })
    }
  }, [sessionId, connected, send])

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
        {rounds.length > 0 && (
          <span className="chip">
            문제 {currentRound?.order_index ?? rounds.filter((r) => r.status === 'closed').length}
            {' / '}
            {rounds.length}
          </span>
        )}
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
          {/* input_type 별 참가자 진행 화면 */}
          {isChat && (
            <ChatPanel
              sessionId={sessionId}
              myUserId={user?.user_id ?? -1}
              round={currentRound}
              showCorrect={isAdmin}
            />
          )}
          {isButton && <ButtonPanel sessionId={sessionId} round={currentRound} />}
          {isTap && <TapPanel sessionId={sessionId} round={currentRound} />}

          {isAdmin && isChat && (
            <ChatJudgePanel
              token={t}
              sessionId={sessionId}
              round={currentRound}
              participantType={game?.participant_type ?? 'team_vs'}
              onScored={refresh}
            />
          )}
          {isAdmin && isTap && (
            <TapOperatorPanel
              token={t}
              sessionId={sessionId}
              round={currentRound}
              participantType={game?.participant_type ?? 'team_vs'}
              onScored={refresh}
            />
          )}

          <h3 className="sec-title">🏆 스코어보드</h3>
          {summary.length === 0 ? (
            <p className="muted">아직 기록된 점수가 없습니다.</p>
          ) : (
            <ol className="board">
              {summary.map((s, i) => (
                <li key={`${s.subject_type}-${s.subject_id}`} className={`row rank-${i + 1}`}>
                  <span className="rank">{i + 1}</span>
                  <span className="name">{subjectLabel(s.subject_type, s.subject_id, s.subject_name)}</span>
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

          {isAdmin && state && (isChat || isButton || isTap) && (
            <RoundOperator
              key={`ro-${sessionId}`}
              token={t}
              sessionId={sessionId}
              rounds={rounds}
              inputType={inputType}
              sessionState={state}
              onChanged={refresh}
              onStateChanged={setState}
            />
          )}

          {isAdmin && state && (
            <OperatorPanel
              key={sessionId}
              token={t}
              sessionId={sessionId}
              state={state}
              teams={teams}
              users={users}
              memberships={memberships}
              participantType={game?.participant_type ?? 'team_vs'}
              onStateChange={setState}
              onScored={refresh}
            />
          )}
        </>
      )}
    </div>
  )
}
