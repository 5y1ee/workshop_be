import { useEffect, useState } from 'react'
import { api, type RewardWithClaims } from '../api'
import { useAuth } from '../auth'
import { useLiveEvent } from '../live'
import { useSeason } from '../season'

export default function DexPage() {
  const { token } = useAuth()
  const t = token as string
  const { seasonId } = useSeason()
  const [rewards, setRewards] = useState<RewardWithClaims[]>([])
  const [selected, setSelected] = useState<RewardWithClaims | null>(null)

  const loadRewards = () => {
    if (seasonId == null) return
    api.rewards(t, seasonId).then(setRewards).catch(() => setRewards([]))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(loadRewards, [t, seasonId])

  // 웹소켓 실시간 업데이트 (도감 탭에 머물 때)
  useLiveEvent(['reward_claimed', 'reward_unclaimed'], loadRewards)

  const revealedCount = rewards.filter((r) => r.is_revealed).length

  return (
    <div className="page">
      <h3 className="sec-title">📕 리워드 도감</h3>

      {rewards.length === 0 ? (
        <p className="muted">이번 시즌에 등록된 보상이 없습니다.</p>
      ) : (
        <>
          <div className="progress">
            공개된 보상 {revealedCount} / {rewards.length}
            <div className="bar">
              <i style={{ width: `${(revealedCount / rewards.length) * 100}%` }} />
            </div>
          </div>

          <div className="dex">
            {rewards.map((r, i) => {
              if (!r.is_revealed) {
                // 미공개
                return (
                  <div key={r.id} className="dexcell locked" onClick={() => setSelected(r)}>
                    <div className="dexno">No.{String(i + 1).padStart(3, '0')}</div>
                    <div className="img">❓</div>
                    <div className="nm">???</div>
                  </div>
                )
              }
              if (r.my_claimed) {
                // 내가 당첨 — 풀 컬러 + 강조 테두리
                return (
                  <div key={r.id} className="dexcell mine" onClick={() => setSelected(r)}>
                    <div className="dexno">No.{String(i + 1).padStart(3, '0')}</div>
                    <div className="img">🎁</div>
                    <div className="nm">{r.name}</div>
                  </div>
                )
              }
              // 공개됐지만 내 것 아님 — 흐릿하게
              return (
                <div key={r.id} className="dexcell others" onClick={() => setSelected(r)}>
                  <div className="dexno">No.{String(i + 1).padStart(3, '0')}</div>
                  <div className="img">🎁</div>
                  <div className="nm">{r.name}</div>
                </div>
              )
            })}
          </div>
          <div className="note">🔒 미공개 보상은 ??? 실루엣으로 표시됩니다.</div>
        </>
      )}

      {selected && (
        <div className="modal" onClick={() => setSelected(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-img">{selected.is_revealed ? '🎁' : '❓'}</div>
            <h3>{selected.is_revealed ? selected.name : '??? (미공개)'}</h3>
            {selected.is_revealed && selected.description && (
              <p className="muted">{selected.description}</p>
            )}
            {selected.is_revealed && (
              <>
                <p className="muted">남은 수량: {selected.remaining_count}개</p>
                {selected.my_claimed && (
                  <p style={{ color: 'var(--accent)', fontWeight: 700 }}>✅ 내가 당첨된 보상입니다!</p>
                )}
              </>
            )}
            <button className="op-btn" onClick={() => setSelected(null)}>
              닫기
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
