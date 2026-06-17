import { useEffect, useState } from 'react'
import {
  api,
  resolveAssetUrl,
  type TeamMember,
  type TeamScore,
  type MyHiddenRole,
  type UserProfile,
  type UserScore,
} from '../api'
import { useAuth } from '../auth'
import { useSeason } from '../season'
import { useLive } from '../live'

export default function MyPage({ onBack }: { onBack?: () => void }) {
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
  const [hiddenRole, setHiddenRole] = useState<MyHiddenRole | null>(null)
  const [hiddenRoleOpen, setHiddenRoleOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<'stats' | 'party'>('stats')

  const loadProfile = () => {
    api.me(t).then(setProfile).catch(() => setProfile(null))
  }
  useEffect(loadProfile, [t])

  const loadTeam = () => {
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
    api.myHiddenRole(t, seasonId).then(setHiddenRole).catch(() => setHiddenRole(null))
  }
  useEffect(loadTeam, [t, seasonId])

  useEffect(() => {
    if (teamId == null) return
    api.teamMembers(t, teamId).then(setMembers).catch(() => setMembers([]))
  }, [t, teamId])

  const loadScoreboard = () => {
    if (seasonId == null) return
    api.seasonScoreboard(t, seasonId).then(setScoreboard).catch(() => setScoreboard([]))
    api.seasonUserScoreboard(t, seasonId).then(setUserScoreboard).catch(() => setUserScoreboard([]))
  }
  useEffect(loadScoreboard, [t, seasonId])
  useEffect(() => {
    if (lastEvent?.type === 'score_recorded' || lastEvent?.type === 'score_changed') {
      loadScoreboard()
      loadProfile()
    }
    if (lastEvent?.type === 'team_membership_changed' && lastEvent.season_id === seasonId) {
      loadTeam()
      loadScoreboard()
    }
    if (
      lastEvent?.type === 'hidden_role_changed' &&
      seasonId != null &&
      (lastEvent.season_id == null || lastEvent.season_id === seasonId)
    ) {
      api.myHiddenRole(t, seasonId).then(setHiddenRole).catch(() => setHiddenRole(null))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastEvent])

  const myRankIdx = scoreboard.findIndex((s) => s.team_id === teamId)
  const myTeamScore = myRankIdx >= 0 ? scoreboard[myRankIdx].total_score : 0
  const myUserRankIdx = userScoreboard.findIndex((s) => s.user_id === user?.user_id)
  const myUserScore = myUserRankIdx >= 0 ? userScoreboard[myUserRankIdx].total_score : 0
  const me = members.find((m) => m.id === user?.user_id)
  const myPoint = profile?.point ?? 0
  const myProfileImage = me?.profile_image ?? profile?.profile_image ?? null
  const userScoreOf = (userId: number) =>
    userScoreboard.find((s) => s.user_id === userId)?.total_score ?? 0

  const maxTeamScore = Math.max(...scoreboard.map((s) => s.total_score), 1)
  const maxUserScore = Math.max(...userScoreboard.map((s) => s.total_score), 1)
  const teamRankPct =
    myRankIdx >= 0 && scoreboard.length > 1
      ? ((scoreboard.length - 1 - myRankIdx) / (scoreboard.length - 1)) * 100
      : myRankIdx === 0 ? 100 : 0
  const userRankPct =
    myUserRankIdx >= 0 && userScoreboard.length > 1
      ? ((userScoreboard.length - 1 - myUserRankIdx) / (userScoreboard.length - 1)) * 100
      : myUserRankIdx === 0 ? 100 : 0
  const teamScorePct = Math.min((myTeamScore / maxTeamScore) * 100, 100)
  const userScorePct = Math.min((myUserScore / maxUserScore) * 100, 100)
  const pointPct = userScorePct

  const membersByScore = [...members].sort(
    (a, b) => userScoreOf(b.id) - userScoreOf(a.id) || a.id - b.id,
  )
  const MEMBER_COLORS = [
    { bg: '#fde7e7', border: '#ee1515' },
    { bg: '#e3f6ec', border: '#2dc35b' },
    { bg: '#e8f3ff', border: '#2a75bb' },
    { bg: '#fff8e6', border: '#f0c040' },
  ]
  const getMemberColor = (memberId: number) => {
    const rank = membersByScore.findIndex((m) => m.id === memberId)
    return MEMBER_COLORS[Math.min(rank, MEMBER_COLORS.length - 1)]
  }

  return (
    <div className="page dex-page">
      <div className="dex-card">
        {/* Teal header */}
        <div className="dex-header">
          <div className="dex-ball-bg" />
          <div className="dex-header-nav">
            <button className="dex-back-btn" onClick={onBack} aria-label="뒤로가기">
              <i className="fa-solid fa-arrow-left-long" />
            </button>
          </div>
          <div className="dex-header-top">
            <div>
              <h2 className="dex-name">{user?.nickname ?? '트레이너'}</h2>
              <div className="dex-badges">
                {teamName && <span className="dex-badge">{teamName}</span>}
                <span className="dex-badge">
                  {user?.role === 'admin' ? '운영자' : '트레이너'}
                </span>
              </div>
            </div>
            <span className="dex-number">
              {myRankIdx >= 0 ? `#${String(myRankIdx + 1).padStart(3, '0')}` : '#—'}
            </span>
          </div>
        </div>

        {/* Avatar floats between header and white card */}
        <div className="dex-avatar-anchor">
          <ProfileFace
            className="dex-avatar"
            profileImage={myProfileImage}
            fallback={user?.role === 'admin' ? '🧑‍✈️' : '🧑'}
            alt={user?.nickname ?? '프로필'}
          />
        </div>

        {/* White card */}
        <div className="dex-white">
          <div className="dex-tabs">
            <button
              className={`dex-tab${activeTab === 'stats' ? ' active' : ''}`}
              onClick={() => setActiveTab('stats')}
            >
              내 스탯
            </button>
            <button
              className={`dex-tab${activeTab === 'party' ? ' active' : ''}`}
              onClick={() => setActiveTab('party')}
            >
              내 파티
            </button>
          </div>

          <div className="dex-content">
            {activeTab === 'stats' ? (
              <div className="dex-stats">
                <DexStat label="내 포인트" value={myPoint} pct={pointPct} colorClass="fill-green" />
                <DexStat label="개인 누적점수" value={myUserScore} pct={userScorePct} colorClass="fill-teal" />
                <DexStat
                  label="팀 순위"
                  value={myRankIdx >= 0 ? `${myRankIdx + 1}위` : '—'}
                  pct={teamRankPct}
                  colorClass="fill-blue"
                />
                <DexStat
                  label="팀 총점"
                  value={myTeamScore}
                  pct={teamScorePct}
                  colorClass="fill-teal"
                />
                <DexStat
                  label="개인 순위"
                  value={myUserRankIdx >= 0 ? `${myUserRankIdx + 1}위` : '—'}
                  pct={userRankPct}
                  colorClass="fill-blue"
                />
                {hiddenRole && (
                  <button
                    className={`hidden-role-card${hiddenRoleOpen ? ' open' : ''}`}
                    onClick={() => setHiddenRoleOpen((v) => !v)}
                  >
                    <span className="hidden-role-kicker">히든 롤</span>
                    <strong>{hiddenRoleOpen ? hiddenRole.name : '숨겨진 미션'}</strong>
                    <span>
                      {hiddenRoleOpen
                        ? hiddenRole.description
                        : '탭해서 내 히든 롤을 확인하세요'}
                    </span>
                    {hiddenRoleOpen && (
                      <em>성공 조건: {hiddenRole.success_condition}</em>
                    )}
                  </button>
                )}
              </div>
            ) : teamId == null ? (
              <p className="muted" style={{ textAlign: 'center', padding: '20px 0' }}>
                아직 팀에 배정되지 않았습니다
              </p>
            ) : members.length === 0 ? (
              <p className="muted" style={{ textAlign: 'center', padding: '20px 0' }}>
                팀원이 없습니다.
              </p>
            ) : (
              <div className="dex-party">
                {membersByScore.map((m) => {
                  const color = getMemberColor(m.id)
                  const memberScore = userScoreOf(m.id)
                  return (
                    <div
                      key={m.id}
                      className={`dex-member${m.id === user?.user_id ? ' me' : ''}`}
                      style={{ background: color.bg, borderColor: color.border }}
                    >
                      <ProfileFace
                        className="dex-member-face"
                        profileImage={m.profile_image}
                        fallback={m.role === 'admin' ? '🧑‍✈️' : '🧑'}
                        alt={m.nickname}
                      />
                      <div className="dex-member-name">{m.nickname}</div>
                      <div className="dex-member-pt">{memberScore}</div>
                      <span className="dex-member-role">
                        {m.role === 'admin' ? '운영자' : '트레이너'}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function DexStat({
  label,
  value,
  pct,
  colorClass,
}: {
  label: string
  value: string | number
  pct: number
  colorClass: string
}) {
  return (
    <div className="dex-stat">
      <span className="dex-stat-label">{label}</span>
      <span className="dex-stat-value">{value}</span>
      <div className="dex-stat-bar">
        <div className={`dex-stat-fill ${colorClass}`} style={{ width: `${Math.max(pct, 4)}%` }} />
      </div>
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
