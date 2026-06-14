import { useEffect, useState } from 'react'
import { api, type TeamMember, type TeamScore } from '../api'
import { useAuth } from '../auth'
import { useSeason } from '../season'
import { useLive } from '../live'

export default function MyPage() {
  const { token, user } = useAuth()
  const t = token as string
  const { seasonId } = useSeason()
  const { lastEvent } = useLive()

  const [teamName, setTeamName] = useState<string | null>(null)
  const [members, setMembers] = useState<TeamMember[]>([])
  const [scoreboard, setScoreboard] = useState<TeamScore[]>([])

  const teamId = user?.team_id ?? null

  // 팀원
  useEffect(() => {
    if (teamId == null) return
    api.teamMembers(t, teamId).then(setMembers).catch(() => setMembers([]))
  }, [t, teamId])

  // 팀 이름 (시즌 팀 목록에서 매핑)
  useEffect(() => {
    if (seasonId == null || teamId == null) return
    api
      .teams(t, seasonId)
      .then((teams) => setTeamName(teams.find((x) => x.id === teamId)?.name ?? null))
      .catch(() => setTeamName(null))
  }, [t, seasonId, teamId])

  // 시즌 누적 점수 (팀 순위/총점)
  const loadScoreboard = () => {
    if (seasonId == null) return
    api.seasonScoreboard(t, seasonId).then(setScoreboard).catch(() => setScoreboard([]))
  }
  useEffect(loadScoreboard, [t, seasonId])
  useEffect(() => {
    if (lastEvent?.type === 'score_recorded') loadScoreboard()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastEvent])

  const myRankIdx = scoreboard.findIndex((s) => s.team_id === teamId)
  const myTeamScore = myRankIdx >= 0 ? scoreboard[myRankIdx].total_score : 0
  const myPoint = members.find((m) => m.id === user?.user_id)?.point ?? 0

  return (
    <div className="page">
      <div className="trainer">
        <div className="flex">
          <div className="avatar">🧑</div>
          <div>
            <div className="t-name">{user?.nickname}</div>
            <span className="pill team">
              {teamName ? `${teamName} · ` : ''}
              {user?.role === 'admin' ? '운영자' : '트레이너'}
            </span>
          </div>
        </div>
        <div className="stat-row">
          <div className="stat">
            <div className="n">{myPoint}</div>
            <div className="l">내 포인트</div>
          </div>
          <div className="stat">
            <div className="n">{myRankIdx >= 0 ? `${myRankIdx + 1}위` : '—'}</div>
            <div className="l">팀 순위</div>
          </div>
          <div className="stat">
            <div className="n">{myTeamScore}</div>
            <div className="l">팀 총점</div>
          </div>
        </div>
      </div>

      {teamId == null ? (
        <p className="muted" style={{ marginTop: 16 }}>
          아직 팀에 배정되지 않았습니다. 운영자가 팀을 배정하면 파티가 표시됩니다.
        </p>
      ) : (
        <>
          <h3 className="sec-title">내 파티 {teamName ? `(${teamName})` : ''}</h3>
          {members.length === 0 ? (
            <p className="muted">팀원이 없습니다.</p>
          ) : (
            <div className="party">
              {members.map((m) => (
                <div key={m.id} className={`slot${m.id === user?.user_id ? ' me' : ''}`}>
                  <div className="face">{m.role === 'admin' ? '🧑‍✈️' : '🧑'}</div>
                  {m.nickname}
                  <br />
                  <b>{m.point}</b>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
