import { useEffect, useState } from 'react'
import { api, ApiError, type GameRound, type ScoreLog, type TapResult } from '../api'
import { useLive } from '../live'

interface Props {
  token: string
  sessionId: number
  round: GameRound | null
  onScored: () => void
}

interface CountRow {
  user_id: number
  nickname: string
  team_name: string | null
  count: number
}

interface SubmittedRow {
  user_id: number
  nickname: string
  team_name: string | null
  value: number
  arrived_at: number
}

export default function TapOperatorPanel({ token, sessionId, round, onScored }: Props) {
  const { subscribe } = useLive()
  const [results, setResults] = useState<TapResult[] | null>(null)
  const [scores, setScores] = useState<ScoreLog[]>([])
  const [targetTime, setTargetTime] = useState<number | null>(null)
  const [signaling, setSignaling] = useState(false)
  const [score, setScore] = useState(10)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  // 실시간 진행 상태
  const [liveCounts, setLiveCounts] = useState<CountRow[]>([])     // count 모드 누적
  const [liveSubmits, setLiveSubmits] = useState<SubmittedRow[]>([]) // speed/timing 도착 순

  const mode = round?.tap_mode ?? null

  useEffect(() => {
    setResults(null)
    setTargetTime(null)
    setSignaling(false)
    setError(null)
    setLiveCounts([])
    setLiveSubmits([])
  }, [round?.id])

  useEffect(() => {
    if (!round) { setScores([]); return }
    api.scores(token, sessionId).then(setScores).catch(() => {})
  }, [round, sessionId, token])

  useEffect(() => {
    return subscribe((e) => {
      if (e.session_id !== sessionId) return

      // 운영자 전용 실시간 이벤트
      if (e.type === 'tap_progress' && e.round_id === round?.id) {
        setLiveCounts((e.counts as CountRow[]) ?? [])
      }
      if (e.type === 'tap_submitted' && e.round_id === round?.id) {
        const row: SubmittedRow = {
          user_id: e.user_id as number,
          nickname: e.nickname as string,
          team_name: (e.team_name as string | null) ?? null,
          value: e.value as number,
          arrived_at: Date.now(),
        }
        setLiveSubmits((prev) => {
          // 중복 방지: 같은 user_id가 이미 있으면 덮어쓰기
          const filtered = prev.filter((p) => p.user_id !== row.user_id)
          return [...filtered, row]
        })
      }

      if (e.type === 'tap_closed' && e.round_id === round?.id) {
        setResults((e.results as TapResult[]) ?? [])
        setTargetTime((e.target_time as number | null) ?? null)
      }
      if (e.type === 'score_recorded' && e.session_id === sessionId) {
        api.scores(token, sessionId).then(setScores).catch(() => {})
        onScored()
      }
    })
  }, [subscribe, sessionId, round?.id, token, onScored])

  const sendSignal = async () => {
    if (!round) return
    setSignaling(true)
    setError(null)
    try {
      await api.sendTapSignal(token, round.id)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
      setSignaling(false)
    }
  }

  const awardedIds = new Set(
    scores
      .filter((s) => s.memo?.includes('tap#'))
      .map((s) => s.subject_id),
  )

  const award = async (r: TapResult) => {
    setBusyId(r.user_id)
    setError(null)
    try {
      await api.createScore(token, sessionId, {
        subject_type: 'user',
        subject_id: r.user_id,
        score,
        memo: `tap#${round?.order_index ?? '-'} ${r.nickname}: ${formatValue(mode, r.value)}`,
      })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusyId(null)
    }
  }

  if (!round) {
    return (
      <section className="op tap-op">
        <h3 className="section">⚡ 탭 게임 결과 (운영자)</h3>
        <p className="muted">진행 중인 라운드가 없습니다.</p>
      </section>
    )
  }

  const isOpen = round.status === 'open'
  const hasResults = !!results

  return (
    <section className="op tap-op">
      <div className="tap-op-head">
        <h3 className="section">⚡ 탭 게임 결과 (운영자)</h3>
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

      <div className="op-block">
        <span className="op-label">
          모드: <strong>{modeLabel(mode)}</strong>
          {mode === 'count' && round.duration && ` · ${round.duration}초`}
          {mode === 'timing' && round.target_time != null && ` · 목표 ${round.target_time.toFixed(1)}초`}
        </span>
      </div>

      {/* speed 모드 신호 버튼 */}
      {mode === 'speed' && isOpen && (
        <div className="op-block">
          <button
            className="op-btn tap-signal-btn"
            disabled={signaling}
            onClick={sendSignal}
          >
            {signaling ? '신호 발송됨 (1~3초 내 발사)' : '🟢 신호 보내기'}
          </button>
        </div>
      )}

      {/* === 라이브 진행 (라운드 open 중, 결과 전) === */}
      {isOpen && !hasResults && mode === 'count' && (
        <div className="op-block">
          <div className="op-label">실시간 누적 카운트 (0.5초 갱신)</div>
          {liveCounts.length === 0 ? (
            <p className="muted">아직 탭한 참가자가 없습니다.</p>
          ) : (
            <table className="tap-result-table">
              <thead>
                <tr className="tap-result-row tap-result-head">
                  <th>순위</th>
                  <th>이름</th>
                  <th>팀</th>
                  <th>누적</th>
                </tr>
              </thead>
              <tbody>
                {liveCounts.map((c, i) => (
                  <tr
                    key={c.user_id}
                    className={`tap-result-row${i === 0 ? ' tap-rank-1' : ''}`}
                  >
                    <td>{i + 1}</td>
                    <td>{c.nickname}</td>
                    <td>{c.team_name ?? '—'}</td>
                    <td>{c.count}회</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {isOpen && !hasResults && (mode === 'speed' || mode === 'timing') && (
        <div className="op-block">
          <div className="op-label">제출 도착 순서 ({liveSubmits.length}명)</div>
          {liveSubmits.length === 0 ? (
            <p className="muted">
              {mode === 'speed' ? '신호 후 제출을 기다리는 중…' : '제출을 기다리는 중…'}
            </p>
          ) : (
            <table className="tap-result-table">
              <thead>
                <tr className="tap-result-row tap-result-head">
                  <th>순번</th>
                  <th>이름</th>
                  <th>팀</th>
                  <th>{valueLabel(mode)}</th>
                </tr>
              </thead>
              <tbody>
                {liveSubmits
                  .slice()
                  .sort((a, b) => a.arrived_at - b.arrived_at)
                  .map((s, i) => (
                    <tr key={s.user_id} className="tap-result-row">
                      <td>{i + 1}</td>
                      <td>{s.nickname}</td>
                      <td>{s.team_name ?? '—'}</td>
                      <td>{formatValue(mode, s.value)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* === 최종 결과 (마감 후) === */}
      {hasResults && (
        <div className="op-block">
          <div className="op-label">
            순위 결과
            {mode === 'timing' && targetTime != null && ` — 목표: ${targetTime.toFixed(1)}초`}
          </div>
          {results!.length === 0 ? (
            <p className="muted">제출 없음</p>
          ) : (
            <table className="tap-result-table">
              <thead>
                <tr className="tap-result-row tap-result-head">
                  <th>순위</th>
                  <th>이름</th>
                  <th>팀</th>
                  <th>{valueLabel(mode)}</th>
                  <th>점수</th>
                </tr>
              </thead>
              <tbody>
                {results!.map((r) => (
                  <tr
                    key={r.user_id}
                    className={`tap-result-row${r.rank === 1 ? ' tap-rank-1' : ''}`}
                  >
                    <td>{r.rank}</td>
                    <td>{r.nickname}</td>
                    <td>{r.team_name ?? '—'}</td>
                    <td>{formatValue(mode, r.value)}</td>
                    <td>
                      <button
                        className="op-btn"
                        disabled={busyId === r.user_id || awardedIds.has(r.user_id)}
                        onClick={() => award(r)}
                      >
                        {awardedIds.has(r.user_id) ? '기록됨' : '점수 기록'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {!isOpen && !hasResults && (
        <p className="muted">라운드를 오픈하세요.</p>
      )}

      {error && <p className="error">{error}</p>}
    </section>
  )
}

function modeLabel(mode: string | null) {
  if (mode === 'count') return '횟수 대결'
  if (mode === 'speed') return '빠르기 대결'
  if (mode === 'timing') return '타이밍 대결'
  return '—'
}

function valueLabel(mode: string | null) {
  if (mode === 'count') return '횟수'
  if (mode === 'speed') return '반응(ms)'
  if (mode === 'timing') return '차이(초)'
  return '기록'
}

function formatValue(mode: string | null, value: number) {
  if (mode === 'count') return `${value}회`
  if (mode === 'speed') return `${Math.round(value)}ms`
  if (mode === 'timing') return `${value.toFixed(1)}초`
  return String(value)
}
