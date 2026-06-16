import { useEffect, useState } from 'react'
import {
  api,
  resolveAssetUrl,
  type TeamMember,
  type TeamScore,
  type UserProfile,
  type UserScore,
} from '../api'
import { useAuth } from '../auth'
import { useSeason } from '../season'
import { useLive } from '../live'

export default function MyPage() {
  const { token, user } = useAuth()
  const t = token as string
  const { seasonId } = useSeason()
  const { lastEvent } = useLive()

  const [teamId, setTeamId] = useState<number | null>(null)
  const [teamName, setTeamName] = useState<string | null>(null)
  const [members, setMembers] = useState<TeamMember[]>([])
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [scoreboard, setScoreboard] = useState<TeamScore[]>([])
  const [userScoreboard, setUserScoreboard] = useState<UserScore[]>([])

  // 내 프로필 (profile_image 포함)
  useEffect(() => {
    api.me(t).then(setProfile).catch(() => setProfile(null))
  }, [t])

  // 선택 시즌에서의 내 팀 (시즌이 바뀌면 따라 바뀐다)
  useEffect(() => {
    if (seasonId == null) return
    setTeamId(null)
    setTeamName(null)
    setMembers([])
    api
      .myTeam(t, seasonId)
      .then((mt) => {
        setTeamId(mt.team_id)
        setTeamName(mt.name)
      })
      .catch(() => setTeamId(null))
  }, [t, seasonId])

  // 팀원
  useEffect(() => {
    if (teamId == null) return
    api.teamMembers(t, teamId).then(setMembers).catch(() => setMembers([]))
  }, [t, teamId])

  // 시즌 누적 점수 (팀 순위/총점)
  const loadScoreboard = () => {
    if (seasonId == null) return
    api.seasonScoreboard(t, seasonId).then(setScoreboard).catch(() => setScoreboard([]))
    api.seasonUserScoreboard(t, seasonId).then(setUserScoreboard).catch(() => setUserScoreboard([]))
  }
  useEffect(loadScoreboard, [t, seasonId])
  useEffect(() => {
    if (lastEvent?.type === 'score_recorded') loadScoreboard()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastEvent])

  const myRankIdx = scoreboard.findIndex((s) => s.team_id === teamId)
  const myTeamScore = myRankIdx >= 0 ? scoreboard[myRankIdx].total_score : 0
  const myUserRankIdx = userScoreboard.findIndex((s) => s.user_id === user?.user_id)
  const myUserScore = myUserRankIdx >= 0 ? userScoreboard[myUserRankIdx].total_score : 0
  const me = members.find((m) => m.id === user?.user_id)
  const myPoint = me?.point ?? profile?.point ?? 0
  const myProfileImage = profile?.profile_image ?? me?.profile_image ?? null

  return (
    <div className="page">
      <div className="trainer">
        <div className="flex">
          <ProfileFace
            className="avatar"
            profileImage={myProfileImage}
            fallback={user?.role === 'admin' ? '🧑‍✈️' : '🧑'}
            alt={user?.nickname ?? '프로필'}
          />
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
          <div className="stat">
            <div className="n">{myUserRankIdx >= 0 ? `${myUserRankIdx + 1}위` : '—'}</div>
            <div className="l">개인 순위</div>
          </div>
          <div className="stat">
            <div className="n">{myUserScore}</div>
            <div className="l">개인 총점</div>
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
                  <ProfileFace
                    className="face"
                    profileImage={m.profile_image}
                    fallback={m.role === 'admin' ? '🧑‍✈️' : '🧑'}
                    alt={m.nickname}
                  />
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

function ProfileFace({
  className,
  profileImage,
  fallback,
  alt,
}: {
  className: string
  profileImage: string | null
  fallback: string
  alt: string
}) {
  const src = resolveAssetUrl(profileImage)
  if (src) {
    return (
      <div className={className}>
        <img src={src} alt={alt} />
      </div>
    )
  }
  return <div className={className}>{fallback}</div>
}
