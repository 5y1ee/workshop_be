import { useEffect, useState } from 'react'
import { api, type Reward } from '../api'
import { useAuth } from '../auth'

// 도감 셀 표시: image_url 이 있으면 공개, 없으면 실루엣(???)
const REVEAL_ICON = '🎁'

export default function DexPage() {
  const { token } = useAuth()
  const t = token as string
  const [rewards, setRewards] = useState<Reward[]>([])
  const [selected, setSelected] = useState<Reward | null>(null)

  useEffect(() => {
    api.rewards(t).then(setRewards).catch(() => setRewards([]))
  }, [t])

  const revealed = (r: Reward) => Boolean(r.image_url)
  const foundCount = rewards.filter(revealed).length

  return (
    <div className="page">
      <h3 className="sec-title">📕 리워드 도감</h3>

      {rewards.length === 0 ? (
        <p className="muted">이번 시즌에 등록된 보상이 없습니다.</p>
      ) : (
        <>
          <div className="progress">
            발견한 보상 {foundCount} / {rewards.length}
            <div className="bar">
              <i style={{ width: `${(foundCount / rewards.length) * 100}%` }} />
            </div>
          </div>

          <div className="dex">
            {rewards.map((r, i) => {
              const open = revealed(r)
              return (
                <div
                  key={r.id}
                  className={`dexcell${open ? '' : ' locked'}`}
                  onClick={() => setSelected(r)}
                >
                  <div className="dexno">No.{String(i + 1).padStart(3, '0')}</div>
                  <div className="img">{open ? REVEAL_ICON : '❓'}</div>
                  <div className="nm">{open ? r.name : '???'}</div>
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
            <div className="modal-img">{revealed(selected) ? REVEAL_ICON : '❓'}</div>
            <h3>{revealed(selected) ? selected.name : '??? (미공개)'}</h3>
            {revealed(selected) && selected.description && (
              <p className="muted">{selected.description}</p>
            )}
            <p className="muted">총 수량: {selected.total_count}개</p>
            <button className="op-btn" onClick={() => setSelected(null)}>
              닫기
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
