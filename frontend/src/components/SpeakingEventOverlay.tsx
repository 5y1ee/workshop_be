import { useCallback, useEffect, useRef, useState } from 'react'
import {
  api,
  ApiError,
  type SpeakingEvent,
  type SpeakingMode,
  type SpeakingResult,
} from '../api'
import { useAuth } from '../auth'
import { useLive } from '../live'
import { useSeason } from '../season'

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

function parseUtcMs(iso: string): number {
  const hasTz = /[Zz]|[+-]\d{2}:?\d{2}$/.test(iso)
  return new Date(hasTz ? iso : iso + 'Z').getTime()
}

function eventFromLive(e: Record<string, unknown>): SpeakingEvent {
  const now = new Date().toISOString()
  return {
    id: e.event_id as number,
    season_id: e.season_id as number,
    mode: e.mode as SpeakingMode,
    status: (e.status as 'open' | 'closed') ?? 'open',
    duration: (e.duration as number | null) ?? null,
    target_time: (e.target_time as number | null) ?? null,
    opened_at: (e.opened_at as string | null) ?? now,
    closed_at: (e.closed_at as string | null) ?? null,
    signal_at: (e.signal_time as string | null) ?? null,
    created_at: now,
    updated_at: null,
  }
}

export default function SpeakingEventOverlay() {
  const { token, user } = useAuth()
  const t = token as string
  const { seasonId } = useSeason()
  const { send, subscribe } = useLive()
  const isAdmin = user?.role === 'admin'

  const [active, setActive] = useState<SpeakingEvent | null>(null)
  const [results, setResults] = useState<SpeakingResult[] | null>(null)
  const [adminOpen, setAdminOpen] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [mode, setMode] = useState<SpeakingMode>('count')
  const [duration, setDuration] = useState('10')
  const [targetTime, setTargetTime] = useState('7.5')

  const [tapCount, setTapCount] = useState(0)
  const [timeLeft, setTimeLeft] = useState<number | null>(null)
  const [signalReceived, setSignalReceived] = useState(false)
  const signalTimeRef = useRef<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const elapsedRef = useRef(0)
  const [showTimer, setShowTimer] = useState(true)
  const [submitted, setSubmitted] = useState(false)
  const [myValue, setMyValue] = useState<number | null>(null)

  const [liveCounts, setLiveCounts] = useState<CountRow[]>([])
  const [liveSubmits, setLiveSubmits] = useState<SubmittedRow[]>([])

  const loadCurrent = useCallback(() => {
    if (seasonId == null) {
      setActive(null)
      return
    }
    api
      .currentSpeakingEvent(t, seasonId)
      .then((event) => {
        setActive(event)
        setResults(null)
      })
      .catch(() => {
        setActive(null)
        setResults(null)
      })
  }, [t, seasonId])

  useEffect(loadCurrent, [loadCurrent])

  useEffect(() => {
    return subscribe((e) => {
      const eventSeason = e.season_id as number | undefined
      if (seasonId == null || eventSeason !== seasonId) return

      if (e.type === 'speaking_event_started') {
        setActive(eventFromLive(e))
        setResults(null)
        setNotice(null)
        setError(null)
        return
      }

      if (e.type === 'speaking_signal' && e.event_id === active?.id) {
        setSignalReceived(true)
        signalTimeRef.current = Date.now()
        setActive((prev) => prev ? { ...prev, signal_at: e.signal_time as string } : prev)
        return
      }

      if (e.type === 'speaking_progress' && e.event_id === active?.id) {
        setLiveCounts((e.counts as CountRow[]) ?? [])
        return
      }

      if (e.type === 'speaking_submitted' && e.event_id === active?.id) {
        const row: SubmittedRow = {
          user_id: e.user_id as number,
          nickname: e.nickname as string,
          team_name: (e.team_name as string | null) ?? null,
          value: e.value as number,
          arrived_at: Date.now(),
        }
        setLiveSubmits((prev) => [...prev.filter((p) => p.user_id !== row.user_id), row])
        return
      }

      if (e.type === 'speaking_event_closed' && e.event_id === active?.id) {
        setActive((prev) =>
          prev
            ? {
                ...prev,
                status: 'closed',
                closed_at: (e.closed_at as string | null) ?? new Date().toISOString(),
              }
            : eventFromLive(e),
        )
        setResults((e.results as SpeakingResult[]) ?? [])
        return
      }

      if (e.type === 'speaking_event_dismissed' && e.event_id === active?.id) {
        clearEvent()
        return
      }

      if (e.type === 'speaking_granted' && e.event_id === active?.id) {
        const grantedUserId = e.user_id as number
        setResults((prev) =>
          prev?.map((r) => (r.user_id === grantedUserId ? { ...r, granted: true } : r)) ?? prev,
        )
        if (grantedUserId === user?.user_id) {
          setNotice('발언권을 받았습니다.')
        }
      }
    })
  }, [subscribe, seasonId, active?.id, user?.user_id])

  useEffect(() => {
    setTapCount(0)
    setTimeLeft(active?.duration ?? null)
    setSignalReceived(!!active?.signal_at)
    signalTimeRef.current = active?.signal_at ? parseUtcMs(active.signal_at) : null
    setElapsed(0)
    elapsedRef.current = 0
    setShowTimer(true)
    setSubmitted(false)
    setMyValue(null)
    setLiveCounts([])
    setLiveSubmits([])
  }, [active?.id])

  useEffect(() => {
    if (active?.mode !== 'count' || active.status !== 'open' || !active.duration) return
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
  }, [active?.id, active?.mode, active?.status, active?.duration, active?.opened_at])

  useEffect(() => {
    if (active?.mode !== 'timing' || active.status !== 'open') return
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
  }, [active?.id, active?.mode, active?.status, active?.opened_at])

  const startEvent = async () => {
    if (seasonId == null) return
    setBusy(true)
    setError(null)
    try {
      const event = await api.createSpeakingEvent(t, seasonId, {
        mode,
        duration: mode === 'count' ? Number(duration) || 10 : null,
        target_time: mode === 'timing' ? Number(targetTime) || 7.5 : null,
      })
      setActive(event)
      setResults(null)
      setAdminOpen(false)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const sendSignal = async () => {
    if (!active) return
    setBusy(true)
    setError(null)
    try {
      await api.sendSpeakingSignal(t, active.id)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const closeEvent = async () => {
    if (!active) return
    setBusy(true)
    setError(null)
    try {
      const closed = await api.closeSpeakingEvent(t, active.id)
      setActive(closed.event)
      setResults(closed.results)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const grant = async (result: SpeakingResult) => {
    if (!active) return
    setBusy(true)
    setError(null)
    try {
      await api.grantSpeakingRight(t, active.id, result.user_id)
      setResults((prev) =>
        prev?.map((r) => (r.user_id === result.user_id ? { ...r, granted: true } : r)) ?? prev,
      )
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const dismissEvent = async () => {
    if (!active) return
    setBusy(true)
    setError(null)
    try {
      await api.dismissSpeakingEvent(t, active.id)
      clearEvent()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const clearEvent = () => {
    setActive(null)
    setResults(null)
    setNotice(null)
    setError(null)
    setAdminOpen(false)
  }

  const press = () => {
    if (!active || active.status !== 'open') return
    if (active.mode === 'count') {
      if ((timeLeft ?? 0) <= 0) return
      setTapCount((c) => c + 1)
      send({ type: 'speaking_press', event_id: active.id })
      return
    }
    if (submitted) return
    if (active.mode === 'speed') {
      if (!signalReceived || signalTimeRef.current == null) return
      const value = Date.now() - signalTimeRef.current
      setMyValue(value)
      setSubmitted(true)
      send({ type: 'speaking_press', event_id: active.id, value })
      return
    }
    const value = elapsedRef.current
    setMyValue(value)
    setSubmitted(true)
    send({ type: 'speaking_press', event_id: active.id, value })
  }

  const isOpen = active?.status === 'open'
  const buttonDisabled =
    !active ||
    !isOpen ||
    (active.mode === 'count' && (timeLeft ?? 0) <= 0) ||
    (active.mode === 'speed' && !signalReceived) ||
    (active.mode !== 'count' && submitted)

  return (
    <>
      {active && (
        <div className="speaking-layer">
          <section className={`speaking-event ${active.status}`}>
            <div className="speaking-head">
              <span className="speaking-kicker">발언권</span>
              <strong>{modeLabel(active.mode)}</strong>
              {active.status === 'closed' && (
                <button className="speaking-close" onClick={() => setActive(null)} aria-label="닫기">
                  ×
                </button>
              )}
            </div>

            {notice && <div className="speaking-notice">{notice}</div>}

            {active.mode === 'count' && isOpen && (
              <div className="speaking-timer">{(timeLeft ?? active.duration ?? 0).toFixed(1)}s</div>
            )}
            {active.mode === 'timing' && isOpen && showTimer && (
              <div className="speaking-timer">{elapsed.toFixed(1)}s</div>
            )}
            {active.mode === 'timing' && isOpen && !showTimer && (
              <div className="speaking-timer muted-clock">?</div>
            )}
            {active.mode === 'speed' && isOpen && (
              <p className="speaking-status">
                {signalReceived ? '지금 누르세요.' : '운영자의 신호를 기다리는 중'}
              </p>
            )}
            {active.mode === 'count' && isOpen && <div className="speaking-count">{tapCount}</div>}

            {isOpen ? (
              <button
                className={`speaking-press${active.mode === 'speed' && signalReceived ? ' signal' : ''}`}
                disabled={buttonDisabled}
                onClick={press}
              >
                {active.mode === 'count' ? '탭!' : active.mode === 'speed' ? (signalReceived ? '지금!' : '대기') : '누르기'}
              </button>
            ) : !isAdmin ? (
              <ResultTable results={results ?? []} mode={active.mode} />
            ) : (
              <p className="speaking-status">결과 확인 및 발언권 부여</p>
            )}

            {submitted && active.mode === 'speed' && myValue != null && (
              <p className="speaking-feedback">반응: {Math.round(myValue)}ms</p>
            )}
            {submitted && active.mode === 'timing' && myValue != null && (
              <p className="speaking-feedback">{myValue.toFixed(1)}초에 눌렀습니다.</p>
            )}

            {isAdmin && (
              <div className="speaking-admin-inline">
                {active.status === 'closed' ? (
                  <>
                    <GrantTable results={results ?? []} mode={active.mode} busy={busy} onGrant={grant} />
                    <button className="op-btn speaking-dismiss-btn" disabled={busy} onClick={dismissEvent}>
                      전체 창 닫기
                    </button>
                    {error && <p className="error">{error}</p>}
                  </>
                ) : (
                  <>
                    <AdminActivePanel
                      event={active}
                      counts={liveCounts}
                      submits={liveSubmits}
                      busy={busy}
                      onSignal={sendSignal}
                      onClose={closeEvent}
                    />
                    {error && <p className="error">{error}</p>}
                  </>
                )}
              </div>
            )}
          </section>
        </div>
      )}

      {isAdmin && !active && (
        <>
          <button className="speaking-fab" onClick={() => setAdminOpen((v) => !v)}>
            발언권
          </button>
          {adminOpen && (
            <div className="speaking-admin-pop">
              <section className="speaking-admin-panel">
                <div className="speaking-admin-title">발언권 이벤트</div>
                {!active ? (
                  <>
                    <label className="speaking-field">
                      <span>모드</span>
                      <select value={mode} onChange={(e) => setMode(e.target.value as SpeakingMode)}>
                        <option value="count">횟수 대결</option>
                        <option value="speed">빠르기 대결</option>
                        <option value="timing">타이밍 대결</option>
                      </select>
                    </label>
                    {mode === 'count' && (
                      <label className="speaking-field">
                        <span>제한 시간(초)</span>
                        <input
                          type="number"
                          min={1}
                          value={duration}
                          onChange={(e) => setDuration(e.target.value)}
                        />
                      </label>
                    )}
                    {mode === 'timing' && (
                      <label className="speaking-field">
                        <span>목표 시간(초)</span>
                        <input
                          type="number"
                          min={0.1}
                          step={0.1}
                          value={targetTime}
                          onChange={(e) => setTargetTime(e.target.value)}
                        />
                      </label>
                    )}
                    <button className="op-btn" disabled={busy || seasonId == null} onClick={startEvent}>
                      시작
                    </button>
                  </>
                ) : null}
                {error && <p className="error">{error}</p>}
              </section>
            </div>
          )}
        </>
      )}
    </>
  )
}

function AdminActivePanel({
  event,
  counts,
  submits,
  busy,
  onSignal,
  onClose,
}: {
  event: SpeakingEvent
  counts: CountRow[]
  submits: SubmittedRow[]
  busy: boolean
  onSignal: () => void
  onClose: () => void
}) {
  return (
    <>
      <div className="speaking-admin-meta">
        {modeLabel(event.mode)}
        {event.mode === 'count' && ` · ${event.duration ?? '-'}초 자동마감`}
        {event.mode === 'timing' && ` · 목표 ${event.target_time?.toFixed(1) ?? '-'}초`}
      </div>
      {event.mode === 'speed' && (
        <button className="op-btn tap-signal-btn" disabled={busy || !!event.signal_at} onClick={onSignal}>
          {event.signal_at ? '신호 발송됨' : '신호 보내기'}
        </button>
      )}
      {event.mode !== 'count' && (
        <button className="op-btn" disabled={busy} onClick={onClose}>
          마감
        </button>
      )}
      {event.mode === 'count' ? (
        <CountTable counts={counts} />
      ) : (
        <SubmitTable submits={submits} mode={event.mode} />
      )}
    </>
  )
}

function CountTable({ counts }: { counts: CountRow[] }) {
  if (counts.length === 0) return <p className="muted">아직 탭한 참가자가 없습니다.</p>
  return (
    <table className="speaking-table">
      <tbody>
        {counts.map((c, i) => (
          <tr key={c.user_id}>
            <td>{i + 1}</td>
            <td>{c.nickname}</td>
            <td>{c.team_name ?? '-'}</td>
            <td>{c.count}회</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function SubmitTable({ submits, mode }: { submits: SubmittedRow[]; mode: SpeakingMode }) {
  if (submits.length === 0) return <p className="muted">제출을 기다리는 중입니다.</p>
  return (
    <table className="speaking-table">
      <tbody>
        {submits
          .slice()
          .sort((a, b) => a.arrived_at - b.arrived_at)
          .map((s, i) => (
            <tr key={s.user_id}>
              <td>{i + 1}</td>
              <td>{s.nickname}</td>
              <td>{s.team_name ?? '-'}</td>
              <td>{formatValue(mode, s.value)}</td>
            </tr>
          ))}
      </tbody>
    </table>
  )
}

function ResultTable({ results, mode }: { results: SpeakingResult[]; mode: SpeakingMode }) {
  if (results.length === 0) return <p className="muted">제출 없음</p>
  return (
    <table className="speaking-table result">
      <tbody>
        {results.slice(0, 5).map((r) => (
          <tr key={r.user_id} className={r.granted ? 'granted' : ''}>
            <td>{r.rank}</td>
            <td>{r.nickname}</td>
            <td>{r.team_name ?? '-'}</td>
            <td>{formatValue(mode, r.value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function GrantTable({
  results,
  mode,
  busy,
  onGrant,
}: {
  results: SpeakingResult[]
  mode: SpeakingMode
  busy: boolean
  onGrant: (r: SpeakingResult) => void
}) {
  if (results.length === 0) return <p className="muted">제출 없음</p>
  return (
    <table className="speaking-table grant">
      <tbody>
        {results.map((r) => (
          <tr key={r.user_id}>
            <td>{r.rank}</td>
            <td>{r.nickname}</td>
            <td>{formatValue(mode, r.value)}</td>
            <td>
              <button className="mini-btn" disabled={busy || r.granted} onClick={() => onGrant(r)}>
                {r.granted ? '부여됨' : '부여'}
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function modeLabel(mode: SpeakingMode) {
  if (mode === 'count') return '횟수 대결'
  if (mode === 'speed') return '빠르기 대결'
  return '타이밍 대결'
}

function formatValue(mode: SpeakingMode, value: number) {
  if (mode === 'count') return `${value}회`
  if (mode === 'speed') return `${Math.round(value)}ms`
  return `${value.toFixed(1)}초`
}
