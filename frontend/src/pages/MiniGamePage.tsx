import { useState } from 'react'

// 프론트 전용 즉석 추첨 — 서버에 저장하지 않는다.
export default function MiniGamePage() {
  const [raw, setRaw] = useState('아론, 지나, 현우, 수민')
  const [angle, setAngle] = useState(0)
  const [spinning, setSpinning] = useState(false)
  const [winner, setWinner] = useState<string | null>(null)

  const names = raw
    .split(/[,\n]/)
    .map((s) => s.trim())
    .filter(Boolean)

  const spin = () => {
    if (names.length < 2 || spinning) return
    setWinner(null)
    const pick = Math.floor(Math.random() * names.length)
    // 여러 바퀴 + 당첨자 위치로 정지
    const turns = 5
    const slice = 360 / names.length
    const target = 360 * turns + (360 - (pick * slice + slice / 2))
    setSpinning(true)
    setAngle((a) => a + target)
    window.setTimeout(() => {
      setSpinning(false)
      setWinner(names[pick])
    }, 3200)
  }

  return (
    <div className="page">
      <h3 className="sec-title">🎲 미니게임 · 대표 선정</h3>
      <div className="mini-tabs">
        <span className="on">🎡 룰렛</span>
        <span className="off">🪜 사다리 (준비중)</span>
      </div>

      <div className="card">
        <div className="op-label">참가자 (쉼표/줄바꿈 구분)</div>
        <textarea
          className="mini-input"
          rows={2}
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
        />

        <div className="wheel-wrap">
          <div
            className="wheel-spin"
            style={{
              transform: `rotate(${angle}deg)`,
              transition: spinning ? 'transform 3.1s cubic-bezier(.17,.67,.2,1)' : 'none',
            }}
          />
          <div className="wheel-pin">▼</div>
          <div className="wheel-hub">{winner ?? 'SPIN'}</div>
        </div>

        <button className="btn-primary" disabled={names.length < 2 || spinning} onClick={spin}>
          {spinning ? '돌리는 중…' : '돌리기 🎯'}
        </button>
        {winner && <p className="winner">🎉 당첨: {winner}</p>}
      </div>

      <div className="note">⚠️ 프론트 전용(JS) 즉석 추첨. 서버에 저장하지 않습니다.</div>
    </div>
  )
}
