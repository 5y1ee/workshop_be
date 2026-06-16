import { useEffect, useRef, useState } from 'react'
import { api, type GachaPullResponse } from '../api'
import { useAuth } from '../auth'
import { useSeason } from '../season'

type Phase = 'idle' | 'pulling' | 'win' | 'blank'

export default function MiniGamePage() {
  const { token, user } = useAuth()
  const t = token as string
  const { seasonId } = useSeason()

  const [point, setPoint] = useState<number | null>(null)
  const [phase, setPhase] = useState<Phase>('idle')
  const [result, setResult] = useState<GachaPullResponse | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    api.me(t).then((p) => setPoint(p.point)).catch(() => setPoint(null))
  }, [t])

  const pull = async () => {
    if (phase === 'pulling' || seasonId == null) return
    setPhase('pulling')
    setResult(null)
    setErrorMsg(null)

    try {
      const res = await api.gachaPull(t, seasonId)
      timerRef.current = setTimeout(() => {
        setResult(res)
        setPoint(res.remaining_point)
        setPhase(res.is_win ? 'win' : 'blank')
      }, 1400)
    } catch (e) {
      setPhase('idle')
      setErrorMsg(e instanceof Error ? e.message : '뽑기 중 오류가 발생했습니다.')
    }
  }

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current) }, [])

  const canPull = phase !== 'pulling' && (point ?? 0) >= 1 && seasonId != null

  return (
    <div className="page">
      <h3 className="sec-title">🎒 뽑기</h3>

      <div className="card" style={{ textAlign: 'center', padding: '24px 16px' }}>
        {/* 포인트 */}
        <p className="muted" style={{ marginBottom: 4, fontSize: 13 }}>
          {user?.nickname}의 보유 포인트
        </p>
        <div style={{ fontSize: 28, fontWeight: 700, marginBottom: 20 }}>
          {point ?? '—'} <span style={{ fontSize: 14, fontWeight: 400 }}>pt</span>
        </div>

        {/* 주머니 */}
        <div className={`gacha-bag-wrap${phase === 'pulling' ? ' pulling' : ''}`}>
          <div className="gacha-bag">
            {/* 주머니 본체 */}
            <svg viewBox="0 0 120 140" width="140" height="160" xmlns="http://www.w3.org/2000/svg">
              {/* 끈 */}
              <path d="M45 28 Q60 10 75 28" fill="none" stroke="#c0a060" strokeWidth="5" strokeLinecap="round"/>
              {/* 주머니 몸통 */}
              <ellipse cx="60" cy="90" rx="48" ry="46" fill="#f5c842"/>
              <ellipse cx="60" cy="90" rx="48" ry="46" fill="none" stroke="#c0a060" strokeWidth="3"/>
              {/* 묶음 부분 */}
              <rect x="42" y="30" width="36" height="18" rx="8" fill="#e8a020"/>
              <rect x="42" y="30" width="36" height="18" rx="8" fill="none" stroke="#c0a060" strokeWidth="2"/>
              {/* 물음표 */}
              {phase === 'idle' || phase === 'pulling' ? (
                <text x="60" y="100" textAnchor="middle" fontSize="40" fill="#c0a060" fontWeight="bold">?</text>
              ) : phase === 'win' ? (
                <text x="60" y="100" textAnchor="middle" fontSize="38">🎉</text>
              ) : (
                <text x="60" y="100" textAnchor="middle" fontSize="38">😢</text>
              )}
            </svg>
          </div>

          {/* 손 */}
          <div className={`gacha-hand${phase === 'pulling' ? ' reach' : ''}`}>
            🤚
          </div>
        </div>

        {/* 결과 텍스트 */}
        <div style={{ minHeight: 64, marginBottom: 8 }}>
          {phase === 'idle' && (
            <p className="muted" style={{ marginTop: 8 }}>주머니에서 뽑아보세요!</p>
          )}
          {phase === 'pulling' && (
            <p className="muted" style={{ marginTop: 8 }}>뽑는 중…</p>
          )}
          {phase === 'win' && result?.reward && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--accent)' }}>
                🎉 당첨!
              </div>
              <div style={{ fontSize: 16, fontWeight: 600, margin: '6px 0' }}>
                {result.reward.name}
              </div>
              {result.reward.description && (
                <p className="muted" style={{ fontSize: 13 }}>{result.reward.description}</p>
              )}
            </div>
          )}
          {phase === 'blank' && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 18 }}>아쉽게도 꽝!</div>
              <p className="muted" style={{ fontSize: 13 }}>다음 기회에 도전하세요.</p>
            </div>
          )}
        </div>

        {errorMsg && (
          <p style={{ color: '#e53', fontSize: 13, margin: '4px 0' }}>{errorMsg}</p>
        )}

        {(phase === 'idle' || phase === 'pulling') && (
          <button
            className="btn-primary"
            disabled={!canPull}
            onClick={pull}
            style={{ width: '100%', marginTop: 4 }}
          >
            {phase === 'pulling'
              ? '뽑는 중…'
              : (point ?? 0) < 1
              ? '포인트 부족'
              : '뽑기! (-1pt)'}
          </button>
        )}

        {(phase === 'win' || phase === 'blank') && (
          <button
            className="op-btn"
            disabled={(point ?? 0) < 1}
            onClick={() => { setPhase('idle'); setResult(null); pull() }}
            style={{ marginTop: 8, width: '100%' }}
          >
            {(point ?? 0) < 1 ? '포인트 부족' : '한 번 더!'}
          </button>
        )}
      </div>

      <div className="note">⚠️ 뽑기 1회당 1포인트 차감. 당첨 결과는 도감에 반영됩니다.</div>

      <style>{`
        .gacha-bag-wrap {
          position: relative;
          width: 160px;
          margin: 0 auto 16px;
          height: 190px;
        }
        .gacha-bag {
          position: absolute;
          top: 0; left: 50%;
          transform: translateX(-50%);
          transition: transform .15s;
        }
        .gacha-bag-wrap.pulling .gacha-bag {
          animation: bagShake .25s ease-in-out 3;
        }
        .gacha-hand {
          position: absolute;
          bottom: 0; right: -8px;
          font-size: 36px;
          transform: rotate(-40deg) translateY(0);
          transition: transform .4s ease-in-out;
          pointer-events: none;
        }
        .gacha-hand.reach {
          animation: handReach 1.4s ease-in-out forwards;
        }
        @keyframes bagShake {
          0%   { transform: translateX(-50%) rotate(0deg); }
          25%  { transform: translateX(-50%) rotate(-6deg); }
          75%  { transform: translateX(-50%) rotate(6deg); }
          100% { transform: translateX(-50%) rotate(0deg); }
        }
        @keyframes handReach {
          0%   { transform: rotate(-40deg) translateY(0); }
          40%  { transform: rotate(-10deg) translateY(-60px) translateX(-20px); }
          70%  { transform: rotate(-10deg) translateY(-60px) translateX(-20px); }
          100% { transform: rotate(-40deg) translateY(0); }
        }
      `}</style>
    </div>
  )
}
