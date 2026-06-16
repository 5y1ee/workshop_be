import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  api,
  ApiError,
  canScoreInState,
  type ChatLog,
  type GameRound,
  type GameState,
  type ScoreLog,
} from '../api'
import { useLive } from '../live'

interface Props {
  token: string
  sessionId: number
  round: GameRound | null
  participantType: string
  state: GameState
  onScored: () => void
}

function timeLabel(value: string) {
  return new Date(value).toLocaleTimeString()
}

/** 운영자 전용: chat 타입 정답 후보 확인 + 점수 확정. */
export default function ChatJudgePanel({
  token,
  sessionId,
  round,
  participantType,
  state,
  onScored,
}: Props) {
  const canScore = canScoreInState(state)
  const { subscribe } = useLive()
  const [logs, setLogs] = useState<ChatLog[]>([])
  const [scores, setScores] = useState<ScoreLog[]>([])
  const [score, setScore] = useState(10)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!round) {
      setLogs([])
      setScores([])
      return
    }
    try {
      const [nextLogs, nextScores] = await Promise.all([
        api.chatLogs(token, sessionId, round.id),
        api.scores(token, sessionId),
      ])
      setLogs(nextLogs)
      setScores(nextScores)
      setError(null)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    }
  }, [round, sessionId, token])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    return subscribe((e) => {
      if (e.type !== 'chat_message' || e.session_id !== sessionId) return
      if (round && e.round_id !== round.id) return
      load()
    })
  }, [load, round, sessionId, subscribe])

  useEffect(() => {
    return subscribe((e) => {
      if (e.type === 'score_recorded' && e.session_id === sessionId) load()
    })
  }, [load, sessionId, subscribe])

  const correctLogs = useMemo(() => logs.filter((log) => log.is_correct), [logs])
  const awardedIds = useMemo(
    () => new Set(scores.map((s) => s.chat_log_id).filter((id): id is number => id != null)),
    [scores],
  )

  const award = async (log: ChatLog) => {
    const scoresTeam = participantType === 'team_vs' || participantType === 'representative'
    if (scoresTeam && log.team_id == null) {
      setError('팀 배정이 없는 유저는 팀 점수를 기록할 수 없습니다.')
      return
    }
    const subjectType = scoresTeam ? 'team' : 'user'
    const subjectId = scoresTeam ? log.team_id! : log.user_id
    setBusyId(log.id)
    setError(null)
    try {
      await api.createScore(token, sessionId, {
        subject_type: subjectType,
        subject_id: subjectId,
        score,
        memo: `노래맞추기 #${round?.order_index ?? '-'} ${log.nickname}: ${log.message}`,
        chat_log_id: log.id,
      })
      onScored()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusyId(null)
    }
  }

  if (!round) {
    return (
      <section className="op judge-panel">
        <h3 className="section">✅ 정답 후보 (운영자)</h3>
        <p className="muted">진행 중인 라운드가 없습니다.</p>
      </section>
    )
  }

  return (
    <section className="op judge-panel">
      <div className="judge-head">
        <h3 className="section">✅ 정답 후보 (운영자)</h3>
        <label className="score-stepper">
          <span>점수</span>
          <input
            type="number"
            value={score}
            min={0}
            onChange={(e) => setScore(Number(e.target.value))}
          />
        </label>
      </div>

      {!canScore && (
        <p className="muted">진행중(in_progress)~보상(reward) 상태에서만 점수를 기록할 수 있습니다.</p>
      )}

      {correctLogs.length === 0 ? (
        <p className="muted">아직 정답 후보가 없습니다.</p>
      ) : (
        <ol className="judge-list">
          {correctLogs.map((log, i) => (
            <li key={log.id} className="judge-item correct">
              <span className="rank">{i + 1}</span>
              <div className="judge-main">
                <strong>{log.team_name ?? log.nickname}</strong>
                <span className="muted">
                  {log.nickname} · {timeLabel(log.server_time)}
                </span>
                <span className="chat-text">{log.message}</span>
              </div>
              <button
                className="op-btn"
                disabled={busyId === log.id || awardedIds.has(log.id) || !canScore}
                onClick={() => award(log)}
              >
                {awardedIds.has(log.id) ? '기록됨' : '점수 기록'}
              </button>
            </li>
          ))}
        </ol>
      )}

      <div className="judge-all">
        <div className="op-label">전체 채팅 ({logs.length})</div>
        {logs.length === 0 ? (
          <p className="muted">아직 메시지가 없습니다.</p>
        ) : (
          <ul className="judge-log-list">
            {logs.map((log) => (
              <li key={log.id} className={log.is_correct ? 'hit' : ''}>
                <span>{timeLabel(log.server_time)}</span>
                <strong>{log.team_name ?? log.nickname}</strong>
                <span>{log.message}</span>
                {log.is_correct && <em>정답</em>}
              </li>
            ))}
          </ul>
        )}
      </div>

      {error && <p className="error">{error}</p>}
    </section>
  )
}
