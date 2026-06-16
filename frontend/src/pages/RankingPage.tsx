import { useEffect, useState } from 'react'
import { api, type TeamScore, type UserScore } from '../api'
import { useAuth } from '../auth'
import { useSeason } from '../season'
import { useLive } from '../live'

type RankMode = 'team' | 'user'
type RankItem = {
  id: number
  name: string
  total_score: number
}

export default function RankingPage() {
  const { token } = useAuth()
  const t = token as string
  const { seasonId } = useSeason()
  const { lastEvent } = useLive()
  const [mode, setMode] = useState<RankMode>('team')
  const [teamBoard, setTeamBoard] = useState<TeamScore[]>([])
  const [userBoard, setUserBoard] = useState<UserScore[]>([])

  const load = () => {
    if (seasonId == null) return
    api.seasonScoreboard(t, seasonId).then(setTeamBoard).catch(() => setTeamBoard([]))
    api.seasonUserScoreboard(t, seasonId).then(setUserBoard).catch(() => setUserBoard([]))
  }
  useEffect(load, [t, seasonId])
  useEffect(() => {
    if (lastEvent?.type === 'score_recorded') load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastEvent])

  const board: RankItem[] = mode === 'team'
    ? teamBoard.map((s) => ({ id: s.team_id, name: s.name, total_score: s.total_score }))
    : userBoard.map((s) => ({ id: s.user_id, name: s.name, total_score: s.total_score }))
  const [first, second, third, ...rest] = board
  const pod = (s: RankItem | undefined, cls: string, medal: string) =>
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
      <div className="mini-tabs rank-tabs">
        <button className={mode === 'team' ? 'on' : 'off'} onClick={() => setMode('team')}>
          팀 랭킹
        </button>
        <button className={mode === 'user' ? 'on' : 'off'} onClick={() => setMode('user')}>
          개인 랭킹
        </button>
      </div>
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
            <div key={s.id} className="rank-row">
              <span className="no">{i + 4}</span>
              <span className="nm">{s.name}</span>
              <span className="sc">{s.total_score}</span>
            </div>
          ))}
          <p className="muted" style={{ marginTop: 8 }}>
            {mode === 'team' ? '시즌 전체 팀 점수' : '시즌 전체 개인 점수'} · 실시간 갱신
          </p>
        </>
      )}
    </div>
  )
}
