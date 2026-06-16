import { useState } from 'react'
import { api, ApiError, type GameRound, type TapMode } from '../api'

interface Props {
  token: string
  sessionId: number
  rounds: GameRound[]
  inputType: string
  onChanged: () => void
}

const STATUS_LABEL: Record<string, string> = {
  waiting: '대기',
  open: '진행중',
  closed: '마감',
}

/** 운영자 전용: 세션의 라운드 생성 / 오픈 / 마감. */
export default function RoundOperator({ token, sessionId, rounds, inputType, onChanged }: Props) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [prompt, setPrompt] = useState('')
  const [options, setOptions] = useState('')
  const [answer, setAnswer] = useState('')

  // tap 전용
  const [tapMode, setTapMode] = useState<TapMode>('count')
  const [duration, setDuration] = useState('10')
  const [targetTime, setTargetTime] = useState('7.5')

  const isButton = inputType === 'button' || inputType === 'vote'
  const isTap = inputType === 'tap'

  const run = async (fn: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
      onChanged()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const addRound = () =>
    run(async () => {
      const opts = isButton
        ? options.split(',').map((s) => s.trim()).filter(Boolean)
        : null
      await api.createRound(token, sessionId, {
        order_index: rounds.length + 1,
        prompt: prompt.trim() || null,
        options: opts && opts.length > 0 ? opts : null,
        correct_answer: !isTap ? answer.trim() || null : null,
        ...(isTap
          ? {
              tap_mode: tapMode,
              duration: tapMode === 'count' ? Number(duration) || null : null,
              target_time: tapMode === 'timing' ? Number(targetTime) || null : null,
            }
          : {}),
      })
      setPrompt('')
      setOptions('')
      setAnswer('')
    })

  return (
    <section className="op">
      <h3 className="section">🎯 라운드 진행 (운영자)</h3>

      {/* 라운드 목록 */}
      {rounds.length === 0 ? (
        <p className="muted">아직 라운드가 없습니다. 아래에서 추가하세요.</p>
      ) : (
        <ul className="round-list">
          {rounds.map((r) => (
            <li key={r.id} className={`round-item ${r.status}`}>
              <div className="round-item-top">
                <span className="round-order">#{r.order_index}</span>
                <span className={`chip status-${r.status}`}>{STATUS_LABEL[r.status]}</span>
                {r.status === 'waiting' && (
                  <button
                    className="op-btn round-action-btn"
                    disabled={busy}
                    onClick={() => run(() => api.openRound(token, r.id).then(() => {}))}
                  >
                    오픈
                  </button>
                )}
                {r.status === 'open' && r.tap_mode !== 'count' && (
                  <button
                    className="op-btn round-action-btn"
                    disabled={busy}
                    onClick={() => run(() => api.closeRound(token, r.id).then(() => {}))}
                  >
                    마감
                  </button>
                )}
                {r.status === 'open' && r.tap_mode === 'count' && (
                  <span className="chip status-open">자동마감</span>
                )}
              </div>
              <div className="round-item-sub">
                {r.tap_mode ? (
                  <span>
                    {r.tap_mode === 'count' && `횟수 · ${r.duration ?? '-'}초`}
                    {r.tap_mode === 'speed' && '빠르기'}
                    {r.tap_mode === 'timing' && `타이밍 · 목표 ${r.target_time?.toFixed(1) ?? '-'}초`}
                  </span>
                ) : (
                  <span className="round-prompt">{r.prompt ?? '(문제 없음)'}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* 라운드 추가 폼 */}
      <div className="op-block">
        <div className="op-label">라운드 추가 (#{rounds.length + 1})</div>

        {/* tap은 문제/힌트 없음 */}
        {!isTap && (
          <input
            className="op-full"
            placeholder={isButton ? '문제 (예: 다음 중 정답은?)' : '문제/힌트 (예: 이 노래 제목은?)'}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
        )}

        {isButton && (
          <input
            className="op-full"
            placeholder="보기 (쉼표 구분, 예: 봄날,Dynamite,첫눈,벚꽃엔딩)"
            value={options}
            onChange={(e) => setOptions(e.target.value)}
          />
        )}

        {!isTap && (
          <input
            className="op-full"
            placeholder="정답 (예: 봄날)"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
          />
        )}

        {isTap && (
          <div className="tap-form">
            <label className="op-label">모드</label>
            <select
              value={tapMode}
              onChange={(e) => setTapMode(e.target.value as TapMode)}
              className="op-full op-select-full"
            >
              <option value="count">횟수 대결 — N초 안에 많이 누르기</option>
              <option value="speed">빠르기 대결 — 신호 후 가장 빠르게</option>
              <option value="timing">타이밍 대결 — 목표 시간에 맞게</option>
            </select>

            {tapMode === 'count' && (
              <>
                <label className="op-label">제한 시간 (초)</label>
                <input
                  type="number"
                  className="op-full"
                  placeholder="예: 10"
                  value={duration}
                  min={3}
                  max={60}
                  onChange={(e) => setDuration(e.target.value)}
                />
              </>
            )}

            {tapMode === 'timing' && (
              <>
                <label className="op-label">목표 시간 (초)</label>
                <input
                  type="number"
                  className="op-full"
                  placeholder="예: 7.5"
                  value={targetTime}
                  step={0.1}
                  min={3.1}
                  onChange={(e) => setTargetTime(e.target.value)}
                />
              </>
            )}
          </div>
        )}

        <button className="op-btn op-btn-add" disabled={busy} onClick={addRound}>
          + 추가
        </button>
      </div>

      {error && <p className="error">{error}</p>}
    </section>
  )
}
