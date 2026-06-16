import { useEffect, useRef, useState } from 'react'
import type { GameRound, TapResult } from '../api'
import { useLive } from '../live'

interface Props {
  sessionId: number
  round: GameRound | null
}

/** timezone 표기가 없는 ISO 문자열은 UTC 로 간주. (백엔드 일부 응답이 naive UTC) */
function parseUtcMs(iso: string): number {
  const hasTz = /[Zz]|[+-]\d{2}:?\d{2}$/.test(iso)
  return new Date(hasTz ? iso : iso + 'Z').getTime()
}

/** WebSocket round_started 이벤트에서 받은 라운드 정보 (prop과 호환되는 부분집합). */
interface LiveRound {
  id: number
  status: string
  tap_mode: string | null
  duration: number | null
  target_time: number | null
  opened_at: string | null
  prompt: string | null
  order_index: number
}

function roundToLive(r: GameRound | null): LiveRound | null {
  if (!r) return null
  return {
    id: r.id,
    status: r.status,
    tap_mode: r.tap_mode,
    duration: r.duration,
    target_time: r.target_time,
    opened_at: r.opened_at,
    prompt: r.prompt,
    order_index: r.order_index,
  }
}

export default function TapPanel({ sessionId, round }: Props) {
  const { send, subscribe } = useLive()

  // round prop / WebSocket 이벤트 둘 다에서 받을 수 있도록 내부 state 유지
  const [active, setActive] = useState<LiveRound | null>(() => roundToLive(round))

  // count 모드
  const [tapCount, setTapCount] = useState(0)
  const [timeLeft, setTimeLeft] = useState<number | null>(null)

  // speed 모드
  const [signalReceived, setSignalReceived] = useState(false)
  const signalTimeRef = useRef<number | null>(null)

  // timing 모드
  const [elapsed, setElapsed] = useState(0)
  const [showTimer, setShowTimer] = useState(true)
  const elapsedRef = useRef(0)

  // 공통
  const [submitted, setSubmitted] = useState(false)
  const [myValue, setMyValue] = useState<number | null>(null)
  const [results, setResults] = useState<TapResult[] | null>(null)
  const [revealedTarget, setRevealedTarget] = useState<number | null>(null)

  // prop 갱신이 오면 (fetch 후) 내부 state 동기화.
  // 단, 라운드가 사라졌다고(round=null) 결과 화면을 꺼뜨리지는 않는다 — 결과 표시 유지.
  useEffect(() => {
    if (round) setActive(roundToLive(round))
  }, [round])

  const mode = active?.tap_mode ?? null

  // 라운드 id 가 진짜 바뀔 때만 진행 상태 초기화 (close → null 사이클에서 results 보존)
  useEffect(() => {
    setTapCount(0)
    setSignalReceived(false)
    signalTimeRef.current = null
    setElapsed(0)
    elapsedRef.current = 0
    setShowTimer(true)
    setSubmitted(false)
    setMyValue(null)
    setResults(null)
    setRevealedTarget(null)
    setTimeLeft(active?.duration ?? null)
  }, [active?.id])

  // WebSocket 이벤트 구독: round_started 로 즉시 활성화 + tap_signal/tap_closed
  useEffect(() => {
    return subscribe((e) => {
      if (e.session_id !== sessionId) return

      // 운영자가 라운드를 오픈한 순간 — fetch 없이도 즉시 패널 활성화
      if (e.type === 'round_started') {
        const next: LiveRound = {
          id: e.round_id as number,
          status: (e.status as string) ?? 'open',
          tap_mode: (e.tap_mode as string | null) ?? null,
          duration: (e.duration as number | null) ?? null,
          target_time: (e.target_time as number | null) ?? null,
          opened_at: (e.opened_at as string | null) ?? null,
          prompt: (e.prompt as string | null) ?? null,
          order_index: (e.order_index as number) ?? 0,
        }
        setActive(next)
        return
      }

      if (e.type === 'tap_signal' && e.round_id === active?.id) {
        setSignalReceived(true)
        signalTimeRef.current = Date.now()
      }

      if (e.type === 'tap_closed' && e.round_id === active?.id) {
        setResults((e.results as TapResult[]) ?? [])
        setRevealedTarget((e.target_time as number | null) ?? null)
      }

      // 마감되면 상태도 closed 로
      if (e.type === 'round_revealed' && e.round_id === active?.id) {
        setActive((a) => (a ? { ...a, status: 'closed' } : a))
      }
    })
  }, [subscribe, sessionId, active?.id])

  // count 모드: opened_at 기준 서버 시간으로 timeLeft 계산 (100ms 간격)
  useEffect(() => {
    if (mode !== 'count' || active?.status !== 'open') return
    if (!active.duration || !active.opened_at) return
    const openedMs = parseUtcMs(active.opened_at)
    const totalMs = active.duration * 1000

    const tick = () => {
      const remainMs = openedMs + totalMs - Date.now()
      const remain = Math.max(0, Math.round(remainMs / 100) / 10)
      setTimeLeft(remain)
      return remain
    }
    tick()
    const id = setInterval(() => {
      if (tick() <= 0) clearInterval(id)
    }, 100)
    return () => clearInterval(id)
  }, [mode, active?.status, active?.duration, active?.opened_at])

  // timing 모드: opened_at 기준 elapsed 계산
  useEffect(() => {
    if (mode !== 'timing' || active?.status !== 'open') return
    if (!active.opened_at) return
    const openedMs = parseUtcMs(active.opened_at)

    const tick = () => {
      const sec = Math.max(0, Math.round((Date.now() - openedMs) / 100) / 10)
      elapsedRef.current = sec
      setElapsed(sec)
      setShowTimer(sec < 3)
    }
    tick()
    const id = setInterval(tick, 100)
    return () => clearInterval(id)
  }, [mode, active?.status, active?.opened_at])

  const handleTap = () => {
    if (!active || active.status !== 'open') return

    if (mode === 'count') {
      if ((timeLeft ?? 0) <= 0) return
      setTapCount((c) => c + 1)
      send({ type: 'tap_press', round_id: active.id })
      return
    }

    if (submitted) return

    if (mode === 'speed') {
      if (!signalReceived || signalTimeRef.current === null) return
      const ms = Date.now() - signalTimeRef.current
      send({ type: 'tap_press', round_id: active.id, elapsed: ms })
      setMyValue(ms)
      setSubmitted(true)
      return
    }

    if (mode === 'timing') {
      const sec = elapsedRef.current
      send({ type: 'tap_press', round_id: active.id, elapsed: sec })
      setMyValue(sec)
      setSubmitted(true)
    }
  }

  if (!active) {
    return (
      <section className="card tappanel">
        <div className="op-label">👆 탭 게임</div>
        <p className="muted">진행 중인 라운드가 없습니다. 운영자가 시작하면 활성화됩니다.</p>
      </section>
    )
  }

  const isActive = active.status === 'open'
  const isDone = !!results || active.status === 'closed'

  const btnDisabled =
    !isActive ||
    isDone ||
    (mode === 'speed' && !signalReceived) ||
    (mode === 'count' && (timeLeft ?? 0) <= 0) ||
    (mode !== 'count' && submitted)

  const btnClass = [
    'tap-btn',
    mode === 'speed' && signalReceived && !submitted ? 'signal' : '',
    submitted || isDone ? 'done' : '',
  ]
    .filter(Boolean)
    .join(' ')

  const btnLabel =
    mode === 'count'
      ? '탭!'
      : mode === 'speed'
        ? signalReceived
          ? '지금!'
          : '대기 중…'
        : '누르기'

  return (
    <section className="card tappanel">
      <div className="op-label">👆 탭 게임 — {modeLabel(mode)}</div>

      {active.prompt && (
        <div className="tap-prompt">
          <strong>문제 {active.order_index}</strong>
          <span className="muted"> · {active.prompt}</span>
        </div>
      )}

      {/* 타이머 */}
      {mode === 'count' && isActive && !isDone && (
        <div className="tap-timer">{(timeLeft ?? active.duration ?? 0).toFixed(1)}s</div>
      )}
      {mode === 'timing' && isActive && !isDone && showTimer && (
        <div className="tap-timer">{elapsed.toFixed(1)}s</div>
      )}
      {mode === 'timing' && isActive && !isDone && !showTimer && (
        <div className="tap-timer tap-timer-hidden">⏱ ?</div>
      )}

      {/* 탭 카운터 (count 모드) */}
      {mode === 'count' && !isDone && (
        <div className="tap-count">{tapCount}</div>
      )}

      {!isDone && (
        <button className={btnClass} disabled={btnDisabled} onClick={handleTap}>
          {btnLabel}
        </button>
      )}

      {submitted && !isDone && mode === 'speed' && myValue !== null && (
        <p className="tap-feedback">반응: {myValue}ms — 결과를 기다리는 중…</p>
      )}
      {submitted && !isDone && mode === 'timing' && myValue !== null && (
        <p className="tap-feedback">{myValue.toFixed(1)}초에 눌렀습니다 — 결과를 기다리는 중…</p>
      )}

      {/* 결과 표시 */}
      {isDone && results && (
        <div className="tap-results">
          <div className="op-label">
            {mode === 'timing' && revealedTarget != null
              ? `목표: ${revealedTarget.toFixed(1)}초`
              : '결과'}
          </div>
          <table className="tap-result-table">
            <thead>
              <tr className="tap-result-row tap-result-head">
                <th>순위</th>
                <th>이름</th>
                <th>팀</th>
                <th>{valueLabel(mode)}</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr
                  key={r.user_id}
                  className={`tap-result-row${r.rank === 1 ? ' tap-rank-1' : ''}`}
                >
                  <td>{r.rank}</td>
                  <td>{r.nickname}</td>
                  <td>{r.team_name ?? '—'}</td>
                  <td>{formatValue(mode, r.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {results.length === 0 && <p className="muted">제출 없음</p>}
        </div>
      )}
    </section>
  )
}

function modeLabel(mode: string | null) {
  if (mode === 'count') return '횟수 대결'
  if (mode === 'speed') return '빠르기 대결'
  if (mode === 'timing') return '타이밍 대결'
  return ''
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
