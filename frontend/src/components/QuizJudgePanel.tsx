import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  api,
  ApiError,
  canScoreInState,
  type GameRound,
  type GameState,
  type QuizSubmission,
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

/** 운영자 전용: button/vote 퀴즈 정답자 확인 + 점수 확정. */
export default function QuizJudgePanel({
  token,
  sessionId,
  round,
  participantType,
  state,
  onScored,
}: Props) {
  const canScore = canScoreInState(state)
  const { subscribe } = useLive()
  const [submissions, setSubmissions] = useState<QuizSubmission[]>([])
  const [scores, setScores] = useState<ScoreLog[]>([])
  const [score, setScore] = useState(10)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  // round prop 이 마감 후 null 이 되어도 결과를 유지하기 위해 마지막 라운드를 보존
  const [stickyRound, setStickyRound] = useState<GameRound | null>(round)
  useEffect(() => {
    if (round) setStickyRound(round)
  }, [round])
  const displayRound = round ?? stickyRound

  const load = useCallback(async () => {
    if (!displayRound) {
      setSubmissions([])
      setScores([])
      return
    }
    try {
      const [subs, nextScores] = await Promise.all([
        api.roundSubmissions(token, displayRound.id),
        api.scores(token, sessionId),
      ])
      setSubmissions(subs)
      setScores(nextScores)
      setError(null)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    }
  }, [displayRound, sessionId, token])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    return subscribe((e) => {
      if (e.session_id !== sessionId) return
      if (
        (e.type === 'submission_progress' && e.round_id === displayRound?.id) ||
        (e.type === 'round_revealed' && e.round_id === displayRound?.id) ||
        e.type === 'score_recorded' ||
        e.type === 'score_changed'
      ) {
        load()
      }
    })
  }, [subscribe, sessionId, displayRound?.id, load])

  const scoresTeam = participantType === 'team_vs' || participantType === 'representative'
  const correctSubs = useMemo(
    () => submissions.filter((s) => s.is_correct),
    [submissions],
  )

  // tap 운영자 패널과 동일하게 memo prefix 로 중복 지급 여부 판정
  const memoPrefix = displayRound ? `quiz#${displayRound.order_index} ` : ''
  const awardedIds = new Set(
    scores
      .filter((s) => memoPrefix !== '' && s.memo?.startsWith(memoPrefix))
      .map((s) => `${s.subject_type}:${s.subject_id}`),
  )

  const award = async (sub: QuizSubmission) => {
    if (scoresTeam && sub.team_id == null) {
      setError('팀 배정이 없는 유저는 팀 점수를 기록할 수 없습니다.')
      return
    }
    const subjectType = scoresTeam ? 'team' : 'user'
    const subjectId = scoresTeam ? sub.team_id! : sub.user_id
    setBusyId(sub.user_id)
    setError(null)
    try {
      const created = await api.createScore(token, sessionId, {
        subject_type: subjectType,
        subject_id: subjectId,
        score,
        memo: `quiz#${displayRound?.order_index ?? '-'} ${sub.nickname}: ${sub.answer}`,
      })
      setScores((prev) => (prev.some((s) => s.id === created.id) ? prev : [...prev, created]))
      onScored()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusyId(null)
    }
  }

  if (!displayRound) {
    return (
      <section className="op judge-panel">
        <h3 className="section">✅ 정답자 (운영자)</h3>
        <p className="muted">진행 중인 라운드가 없습니다.</p>
      </section>
    )
  }

  const awardKey = (sub: QuizSubmission) =>
    `${scoresTeam ? 'team' : 'user'}:${scoresTeam ? sub.team_id : sub.user_id}`

  return (
    <section className="op judge-panel">
      <div className="judge-head">
        <h3 className="section">✅ 정답자 (운영자)</h3>
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

      {correctSubs.length === 0 ? (
        <p className="muted">아직 정답자가 없습니다.</p>
      ) : (
        <ol className="judge-list">
          {correctSubs.map((sub, i) => (
            <li key={sub.user_id} className="judge-item correct">
              <span className="rank">{i + 1}</span>
              <div className="judge-main">
                <strong>{sub.team_name ?? sub.nickname}</strong>
                <span className="muted">{sub.nickname}</span>
                <span className="chat-text">{sub.answer}</span>
              </div>
              <button
                className="op-btn"
                disabled={busyId === sub.user_id || awardedIds.has(awardKey(sub)) || !canScore}
                onClick={() => award(sub)}
              >
                {awardedIds.has(awardKey(sub)) ? '기록됨' : '점수 기록'}
              </button>
            </li>
          ))}
        </ol>
      )}

      <div className="judge-all">
        <div className="op-label">전체 제출 ({submissions.length})</div>
        {submissions.length === 0 ? (
          <p className="muted">아직 제출이 없습니다.</p>
        ) : (
          <ul className="judge-log-list">
            {submissions.map((sub) => (
              <li key={sub.user_id} className={sub.is_correct ? 'hit' : ''}>
                <strong>{sub.team_name ?? sub.nickname}</strong>
                <span>{sub.answer}</span>
                {sub.is_correct && <em>정답</em>}
              </li>
            ))}
          </ul>
        )}
      </div>

      {error && <p className="error">{error}</p>}
    </section>
  )
}
