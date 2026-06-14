import { useEffect, useState } from 'react'
import { api, type TeamScore } from '../api'
import { useAuth } from '../auth'
import { useSeason } from '../season'
import { useLive } from '../live'

export default function RankingPage() {
  const { token } = useAuth()
  const t = token as string
  const { seasonId } = useSeason()
  const { lastEvent } = useLive()
  const [board, setBoard] = useState<TeamScore[]>([])

  const load = () => {
    if (seasonId == null) return
    api.seasonScoreboard(t, seasonId).then(setBoard).catch(() => setBoard([]))
  }
  useEffect(load, [t, seasonId])
  useEffect(() => {
    if (lastEvent?.type === 'score_recorded') load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastEvent])

  const [first, second, third, ...rest] = board
  const pod = (s: TeamScore | undefined, cls: string, medal: string) =>
    s ? (
      <div className={`pod ${cls}`}>
        <div className="face">{medal}</div>
        <div className="nm">{s.name}</div>
        <div className="sc">{s.total_score}</div>
      </div>
    ) : (
      <div className={`pod ${cls}`} />
    )

  return (
    <div className="page">
      <h3 className="sec-title">🏆 명예의 전당</h3>
      {board.length === 0 ? (
        <p className="muted">아직 점수가 없습니다.</p>
      ) : (
        <>
          <div className="podium">
            {pod(second, 'p2', '🥈')}
            {pod(first, 'p1', '👑')}
            {pod(third, 'p3', '🥉')}
          </div>
          {rest.map((s, i) => (
            <div key={s.team_id} className="rank-row">
              <span className="no">{i + 4}</span>
              <span className="nm">{s.name}</span>
              <span className="sc">{s.total_score}</span>
            </div>
          ))}
          <p className="muted" style={{ marginTop: 8 }}>
            시즌 전체 게임 합산 점수 · 실시간 갱신
          </p>
        </>
      )}
    </div>
  )
}
