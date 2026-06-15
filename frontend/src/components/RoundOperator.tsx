import { useState } from 'react'
import { api, ApiError, type GameRound } from '../api'

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

  const isButton = inputType === 'button' || inputType === 'vote'

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
        correct_answer: answer.trim() || null,
      })
      setPrompt('')
      setOptions('')
      setAnswer('')
    })

  return (
    <section className="op">
      <h3 className="section">🎯 라운드 진행 (운영자)</h3>

      {rounds.length === 0 ? (
        <p className="muted">아직 라운드가 없습니다. 아래에서 추가하세요.</p>
      ) : (
        <ul className="round-list">
          {rounds.map((r) => (
            <li key={r.id} className={`round-item ${r.status}`}>
              <span className="round-order">#{r.order_index}</span>
              <span className="round-prompt">{r.prompt ?? '(문제 없음)'}</span>
              <span className={`chip status-${r.status}`}>{STATUS_LABEL[r.status]}</span>
              {r.status === 'waiting' && (
                <button
                  className="op-btn"
                  disabled={busy}
                  onClick={() => run(() => api.openRound(token, r.id).then(() => {}))}
                >
                  오픈
                </button>
              )}
              {r.status === 'open' && (
                <button
                  className="op-btn"
                  disabled={busy}
                  onClick={() => run(() => api.closeRound(token, r.id).then(() => {}))}
                >
                  마감·정답공개
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="op-block">
        <div className="op-label">라운드 추가 (#{rounds.length + 1})</div>
        <input
          className="op-full"
          placeholder="문제/힌트 (예: 이 노래 제목은?)"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        {isButton && (
          <input
            className="op-full"
            placeholder="보기 (쉼표 구분, 예: 봄날,Dynamite,첫눈,벚꽃엔딩)"
            value={options}
            onChange={(e) => setOptions(e.target.value)}
          />
        )}
        <input
          className="op-full"
          placeholder="정답 (예: 봄날)"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
        />
        <button className="op-btn" disabled={busy} onClick={addRound}>
          추가
        </button>
      </div>

      {error && <p className="error">{error}</p>}
    </section>
  )
}
