import { useCallback, useEffect, useState, type CSSProperties } from 'react'
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  api,
  ApiError,
  type Game,
  type Buff,
  type GameSession,
  type HiddenRole,
  type HiddenRoleAssignment,
  type Notice,
  type QuizCatalog,
  type Reward,
  type RewardClaimDetail,
  type SeasonMembership,
  type Team,
  type TeamBuff,
  type TimetableEntry,
  type UserProfile,
  type UserStatus,
} from '../api'
import { useAuth } from '../auth'
import { useLiveEvent } from '../live'
import { useSeason } from '../season'

interface Props {
  onClose: () => void
}

const STATUS_LABEL: Record<string, string> = {
  preparing: '준비중',
  active: '진행중',
  done: '종료',
}

/** 드래그로 순서를 바꿀 수 있는 타임테이블 한 줄. */
function SortableEntryRow({
  id,
  order,
  title,
  modeLabel,
  mainVisible,
  busy,
  onToggleVisible,
  onDelete,
}: {
  id: number
  order: number
  title: string
  modeLabel: string
  mainVisible: boolean
  busy: boolean
  onToggleVisible: (id: number, nextVisible: boolean) => void
  onDelete: (id: number) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id })
  const style: CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
  }
  return (
    <div ref={setNodeRef} style={style} className="admin-row">
      <button
        className="mini-btn ghost"
        style={{ cursor: 'grab', touchAction: 'none', padding: '0 8px' }}
        aria-label="드래그해 순서 변경"
        {...attributes}
        {...listeners}
      >
        ⠿
      </button>
      <span className="row-main">
        <b>{order}. {title}</b>
        <span className="chip">{modeLabel}</span>
      </span>
      <button
        className={`mini-btn ${mainVisible ? '' : 'ghost'}`}
        disabled={busy}
        onClick={() => onToggleVisible(id, !mainVisible)}
      >
        {mainVisible ? '메인 표시' : '메인 숨김'}
      </button>
      <button className="mini-btn danger" disabled={busy} onClick={() => onDelete(id)}>
        삭제
      </button>
    </div>
  )
}

function TeamBuffAssignRow({
  entryId,
  title,
  hasSession,
  teams,
  buffs,
  busy,
  onAssign,
}: {
  entryId: number
  title: string
  hasSession: boolean
  teams: Team[]
  buffs: Buff[]
  busy: boolean
  onAssign: (entryId: number, teamId: string, buffId: string) => void
}) {
  const [teamId, setTeamId] = useState('')
  const [buffId, setBuffId] = useState('')
  return (
    <div className="admin-row">
      <span className="row-main">
        <b>{title}</b>
        {!hasSession && <span className="muted">세션 필요</span>}
      </span>
      <select className="assign" value={teamId} disabled={busy || !hasSession} onChange={(e) => setTeamId(e.target.value)}>
        <option value="">팀</option>
        {teams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}
      </select>
      <select className="assign" value={buffId} disabled={busy || !hasSession} onChange={(e) => setBuffId(e.target.value)}>
        <option value="">버프/디버프</option>
        {buffs.map((buff) => <option key={buff.id} value={buff.id}>{buff.name}</option>)}
      </select>
      <button className="mini-btn" disabled={busy || !hasSession} onClick={() => onAssign(entryId, teamId, buffId)}>
        부여
      </button>
    </div>
  )
}

export default function AdminPage({ onClose }: Props) {
  const { token } = useAuth()
  const t = token as string
  const { seasons, seasonId, setSeasonId, refresh: refreshSeasons } = useSeason()
  const selectedSeason = seasons.find((s) => s.id === seasonId) ?? null

  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [adminTab, setAdminTab] = useState<
    'season' | 'teams' | 'timetable' | 'rewards' | 'users' | 'hidden' | 'buffs' | 'notices' | 'quiz' | 'reset'
  >('teams')
  const [resetConfirm, setResetConfirm] = useState('')
  const [resetMessage, setResetMessage] = useState<string | null>(null)

  const run = async (fn: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  // 인라인 이름 수정 (시즌/팀 공용)
  const [edit, setEdit] = useState<{ kind: 'season' | 'team'; id: number } | null>(null)
  const [editValue, setEditValue] = useState('')
  const startEdit = (kind: 'season' | 'team', id: number, value: string) => {
    setEdit({ kind, id })
    setEditValue(value)
  }

  // ---------- 시즌 ----------
  const [seasonName, setSeasonName] = useState('')

  const createSeason = () =>
    run(async () => {
      if (!seasonName.trim()) throw new ApiError(400, '시즌 이름을 입력하세요.')
      const s = await api.createSeason(t, seasonName.trim())
      setSeasonName('')
      await refreshSeasons()
      setSeasonId(s.id)
    })

  const resetOperationalData = () =>
    run(async () => {
      if (resetConfirm !== '운영 데이터 초기화') {
        throw new ApiError(400, '확인 문구를 정확히 입력하세요.')
      }
      const res = await api.resetOperationalData(t)
      setResetMessage(res.message)
      setResetConfirm('')
      await refreshSeasons()
      loadUsers()
      loadGames()
      loadTeams()
      loadMemberships()
      loadEntries()
      loadRewards()
      loadNotices()
      loadUserStatus()
    })

  const activateSeason = (id: number) =>
    run(async () => {
      await api.updateSeason(t, id, { status: 'active' })
      await refreshSeasons()
    })

  const renameSeason = (id: number) =>
    run(async () => {
      await api.updateSeason(t, id, { name: editValue.trim() })
      setEdit(null)
      await refreshSeasons()
    })

  const deleteSeason = (id: number) =>
    run(async () => {
      if (!confirm('이 시즌을 삭제할까요? (소프트 삭제)')) return
      await api.deleteSeason(t, id)
      await refreshSeasons()
    })

  // ---------- 팀 ----------
  const [teams, setTeams] = useState<Team[]>([])
  const [teamName, setTeamName] = useState('')

  const loadTeams = useCallback(() => {
    if (seasonId == null) {
      setTeams([])
      return
    }
    api.teams(t, seasonId).then(setTeams).catch(() => setTeams([]))
  }, [t, seasonId])
  useEffect(loadTeams, [loadTeams])

  const createTeam = () =>
    run(async () => {
      if (seasonId == null) throw new ApiError(400, '먼저 시즌을 선택/생성하세요.')
      if (!teamName.trim()) throw new ApiError(400, '팀 이름을 입력하세요.')
      await api.createTeam(t, seasonId, teamName.trim())
      setTeamName('')
      loadTeams()
    })

  const renameTeam = (id: number) =>
    run(async () => {
      await api.updateTeam(t, id, editValue.trim())
      setEdit(null)
      loadTeams()
    })

  const deleteTeam = (id: number) =>
    run(async () => {
      if (!confirm('이 팀을 삭제할까요? (소속 멤버 배정은 해제됩니다)')) return
      await api.deleteTeam(t, id)
      loadTeams()
      loadMemberships()
    })

  // ---------- 유저 배치 (멤버십) ----------
  const [users, setUsers] = useState<UserProfile[]>([])
  const [memberships, setMemberships] = useState<SeasonMembership[]>([])
  const [userStatus, setUserStatus] = useState<UserStatus[]>([])
  const [gachaCost, setGachaCost] = useState('1')
  const [hiddenRoles, setHiddenRoles] = useState<HiddenRole[]>([])
  const [hiddenAssignments, setHiddenAssignments] = useState<HiddenRoleAssignment[]>([])
  const [newHiddenRole, setNewHiddenRole] = useState({
    name: '',
    description: '',
    success_condition: '',
  })
  const [buffs, setBuffs] = useState<Buff[]>([])
  const [teamBuffs, setTeamBuffs] = useState<TeamBuff[]>([])
  const [newBuff, setNewBuff] = useState({
    name: '',
    description: '',
    type: 'buff' as 'buff' | 'debuff',
    effect_type: 'action_restrict',
    duration: 'next_game',
  })
  const [entrySessions, setEntrySessions] = useState<Record<number, GameSession | null>>({})
  const [notices, setNotices] = useState<Notice[]>([])
  const [noticeMessage, setNoticeMessage] = useState('')
  const [noticeDuration, setNoticeDuration] = useState('10')

  const loadUsers = useCallback(() => {
    api.users(t).then(setUsers).catch(() => setUsers([]))
  }, [t])
  useEffect(loadUsers, [loadUsers])

  const loadMemberships = useCallback(() => {
    if (seasonId == null) {
      setMemberships([])
      return
    }
    api.seasonMembers(t, seasonId).then(setMemberships).catch(() => setMemberships([]))
  }, [t, seasonId])
  useEffect(loadMemberships, [loadMemberships])

  const loadUserStatus = useCallback(() => {
    if (seasonId == null) {
      setUserStatus([])
      return
    }
    api.seasonUserStatus(t, seasonId).then(setUserStatus).catch(() => setUserStatus([]))
  }, [t, seasonId])
  useEffect(loadUserStatus, [loadUserStatus])
  useEffect(() => {
    setGachaCost(String(selectedSeason?.gacha_pull_cost ?? 1))
  }, [selectedSeason])

  const loadHiddenRoles = useCallback(() => {
    api.hiddenRoles(t).then(setHiddenRoles).catch(() => setHiddenRoles([]))
  }, [t])
  useEffect(loadHiddenRoles, [loadHiddenRoles])

  const loadHiddenAssignments = useCallback(() => {
    if (seasonId == null) {
      setHiddenAssignments([])
      return
    }
    api.hiddenRoleAssignments(t, seasonId).then(setHiddenAssignments).catch(() => setHiddenAssignments([]))
  }, [t, seasonId])
  useEffect(loadHiddenAssignments, [loadHiddenAssignments])

  const loadBuffs = useCallback(() => {
    api.buffs(t).then(setBuffs).catch(() => setBuffs([]))
  }, [t])
  useEffect(loadBuffs, [loadBuffs])

  const loadTeamBuffs = useCallback(() => {
    if (seasonId == null) {
      setTeamBuffs([])
      return
    }
    api.seasonTeamBuffs(t, seasonId).then(setTeamBuffs).catch(() => setTeamBuffs([]))
  }, [t, seasonId])
  useEffect(loadTeamBuffs, [loadTeamBuffs])

  const loadNotices = useCallback(() => {
    if (seasonId == null) {
      setNotices([])
      return
    }
    api.notices(t, seasonId).then(setNotices).catch(() => setNotices([]))
  }, [t, seasonId])
  useEffect(loadNotices, [loadNotices])

  // ---------- 퀴즈 문제 데이터 ----------
  const [quizCatalog, setQuizCatalog] = useState<QuizCatalog | null>(null)
  const [quizCats, setQuizCats] = useState<string[]>([])
  const [quizLimit, setQuizLimit] = useState('20')
  const [quizCreateSession, setQuizCreateSession] = useState(true)
  const [quizMessage, setQuizMessage] = useState<string | null>(null)
  const [quizOpenCat, setQuizOpenCat] = useState<string | null>(null)

  const loadQuizCatalog = useCallback(() => {
    api.quizCatalog(t).then(setQuizCatalog).catch(() => setQuizCatalog(null))
  }, [t])
  useEffect(loadQuizCatalog, [loadQuizCatalog])

  const toggleQuizCat = (name: string) =>
    setQuizCats((prev) =>
      prev.includes(name) ? prev.filter((c) => c !== name) : [...prev, name],
    )

  const seedQuiz = (
    opts: { categories?: string[]; limit?: number; shuffle?: boolean; replace?: boolean },
  ) =>
    run(async () => {
      if (seasonId == null) throw new ApiError(400, '먼저 시즌을 선택하세요.')
      setQuizMessage(null)
      const res = await api.quizSeed(t, {
        season_id: seasonId,
        create_session: quizCreateSession,
        ...opts,
      })
      setQuizMessage(
        `✅ ${res.seeded}문제 적재 (세션 #${res.session_id}, 순서 ${res.start_order}~)` +
          (res.removed ? ` · 기존 대기 ${res.removed}개 교체` : ''),
      )
      loadEntries()
    })

  const teamOf = (userId: number) =>
    memberships.find((m) => m.user_id === userId)?.team_id ?? null

  const assign = (userId: number, value: string) =>
    run(async () => {
      if (seasonId == null) return
      if (value === '') {
        await api.unassignMember(t, seasonId, userId)
      } else {
        await api.assignMember(t, seasonId, Number(value), userId)
      }
      loadMemberships()
      loadUserStatus()
    })

  const [nu, setNu] = useState({ username: '', nickname: '', password: '' })
  const createUser = () =>
    run(async () => {
      if (!nu.username.trim() || !nu.nickname.trim() || !nu.password.trim())
        throw new ApiError(400, '아이디·닉네임·비밀번호를 모두 입력하세요.')
      await api.createUser(t, {
        username: nu.username.trim(),
        nickname: nu.nickname.trim(),
        password: nu.password.trim(),
        role: 'user',
      })
      setNu({ username: '', nickname: '', password: '' })
      loadUsers()
      loadUserStatus()
    })

  const saveGachaCost = () =>
    run(async () => {
      if (seasonId == null) return
      const value = Number(gachaCost)
      if (!Number.isFinite(value) || value < 1) {
        throw new ApiError(400, '뽑기 차감 포인트는 1 이상이어야 합니다.')
      }
      await api.updateSeason(t, seasonId, { gacha_pull_cost: Math.floor(value) })
      await refreshSeasons()
    })

  const createHiddenRole = () =>
    run(async () => {
      if (!newHiddenRole.name.trim() || !newHiddenRole.description.trim()) {
        throw new ApiError(400, '히든롤 이름과 설명을 입력하세요.')
      }
      await api.createHiddenRole(t, {
        name: newHiddenRole.name.trim(),
        description: newHiddenRole.description.trim(),
        scope: 'global',
        success_condition: newHiddenRole.success_condition.trim() || '운영자 판정',
      })
      setNewHiddenRole({ name: '', description: '', success_condition: '' })
      loadHiddenRoles()
    })

  const assignHiddenRole = (userId: number, value: string) =>
    run(async () => {
      if (seasonId == null) return
      if (value === '') {
        await api.unassignHiddenRole(t, seasonId, userId)
      } else {
        await api.assignHiddenRole(t, seasonId, userId, Number(value))
      }
      loadHiddenAssignments()
    })

  const createBuff = () =>
    run(async () => {
      if (!newBuff.name.trim() || !newBuff.description.trim()) {
        throw new ApiError(400, '버프/디버프 이름과 설명을 입력하세요.')
      }
      await api.createBuff(t, {
        ...newBuff,
        name: newBuff.name.trim(),
        description: newBuff.description.trim(),
      })
      setNewBuff({
        name: '',
        description: '',
        type: 'buff',
        effect_type: 'action_restrict',
        duration: 'next_game',
      })
      loadBuffs()
    })

  const assignTeamBuff = (entryId: number, teamId: string, buffId: string) =>
    run(async () => {
      const session = entrySessions[entryId]
      if (!session) throw new ApiError(400, '먼저 해당 게임 세션을 생성하세요.')
      if (!teamId || !buffId) throw new ApiError(400, '팀과 버프/디버프를 선택하세요.')
      await api.assignTeamBuff(t, session.id, Number(teamId), Number(buffId))
      loadTeamBuffs()
    })

  const createNotice = () =>
    run(async () => {
      if (seasonId == null) throw new ApiError(400, '먼저 시즌을 선택하세요.')
      if (!noticeMessage.trim()) throw new ApiError(400, '공지 내용을 입력하세요.')
      const duration = Number(noticeDuration)
      if (!Number.isFinite(duration) || duration < 1) {
        throw new ApiError(400, '공지 유지 시간은 1분 이상이어야 합니다.')
      }
      await api.createNotice(t, seasonId, {
        message: noticeMessage.trim(),
        duration_minutes: Math.floor(duration),
      })
      setNoticeMessage('')
      setNoticeDuration('10')
      loadNotices()
    })

  const deleteNotice = (noticeId: number) =>
    run(async () => {
      await api.deleteNotice(t, noticeId)
      loadNotices()
    })

  // ---------- 타임테이블 ----------
  const [entries, setEntries] = useState<TimetableEntry[]>([])
  const [games, setGames] = useState<Game[]>([])
  const [pickGame, setPickGame] = useState('')
  const [pickLabel, setPickLabel] = useState('')
  const [pickScoreMode, setPickScoreMode] = useState<'' | 'team' | 'individual'>('')
  // 클릭(작은 움직임)은 드래그로 오인하지 않도록 8px 이동 후 드래그 시작
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  )

  const loadEntries = useCallback(() => {
    if (seasonId == null) {
      setEntries([])
      return
    }
    api.timetable(t, seasonId)
      .then(async (list) => {
        setEntries(list)
        const pairs = await Promise.all(
          list.map(async (entry) => {
            const sessions = await api.sessions(t, entry.id).catch(() => [])
            return [entry.id, sessions.length ? sessions[sessions.length - 1] : null] as const
          }),
        )
        setEntrySessions(Object.fromEntries(pairs))
      })
      .catch(() => {
        setEntries([])
        setEntrySessions({})
      })
  }, [t, seasonId])
  useEffect(loadEntries, [loadEntries])
  const loadGames = useCallback(() => {
    api.games(t).then(setGames).catch(() => setGames([]))
  }, [t])
  useEffect(loadGames, [loadGames])
  const sortedEntries = entries.slice().sort((a, b) => a.order_index - b.order_index)

  // 같은 게임이 이미 타임테이블에 있으면 "제목 N"을 기본 라벨로 제안 (오프라인 게임 다회 진행용)
  const suggestLabel = (gameId: string) => {
    const g = games.find((x) => x.id === Number(gameId))
    if (!g) return ''
    const same = entries.filter((e) => e.game_id === Number(gameId)).length
    return same > 0 ? `${g.title} ${same + 1}` : g.title
  }

  // 게임의 participant_type으로 팀전/개인전 기본값을 제안 (운영자가 바꿀 수 있음)
  const defaultScoreMode = (gameId: string): '' | 'team' | 'individual' => {
    const g = games.find((x) => x.id === Number(gameId))
    if (!g) return ''
    return g.participant_type === 'team_vs' || g.participant_type === 'representative'
      ? 'team'
      : 'individual'
  }

  const onPickGame = (gameId: string) => {
    setPickGame(gameId)
    setPickLabel(suggestLabel(gameId))
    setPickScoreMode(defaultScoreMode(gameId))
  }

  const addEntry = () =>
    run(async () => {
      if (seasonId == null) throw new ApiError(400, '먼저 시즌을 선택하세요.')
      if (!pickGame) throw new ApiError(400, '게임을 선택하세요.')
      const game = games.find((g) => g.id === Number(pickGame))
      await api.createTimetable(t, seasonId, {
        game_id: Number(pickGame),
        order_index: entries.length + 1,
        label: pickLabel.trim() || (game ? game.title : null),
        score_mode: pickScoreMode || null,
      })
      setPickGame('')
      setPickLabel('')
      setPickScoreMode('')
      loadEntries()
    })

  const deleteEntry = (id: number) =>
    run(async () => {
      if (!confirm('이 게임을 진행 목록에서 삭제할까요? 이미 세션이 생성된 항목은 삭제할 수 없습니다.')) {
        return
      }
      await api.deleteTimetable(t, id)
      loadEntries()
    })

  const toggleEntryVisible = (id: number, nextVisible: boolean) =>
    run(async () => {
      setEntries((prev) =>
        prev.map((entry) =>
          entry.id === id ? { ...entry, main_visible: nextVisible } : entry,
        ),
      )
      await api.updateTimetable(t, id, { main_visible: nextVisible })
      loadEntries()
    })

  // 드래그로 배열 순서를 바꾼 뒤 order_index 를 1..N 으로 다시 매겨 저장한다.
  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const sorted = entries.slice().sort((a, b) => a.order_index - b.order_index)
    const from = sorted.findIndex((e) => e.id === active.id)
    const to = sorted.findIndex((e) => e.id === over.id)
    if (from === -1 || to === -1) return

    const moved = arrayMove(sorted, from, to)
    // 낙관적 업데이트: 화면을 먼저 새 순서로 갱신
    const reindexed = moved.map((e, i) => ({ ...e, order_index: i + 1 }))
    setEntries(reindexed)

    run(async () => {
      // order_index 가 실제로 바뀐 항목만 저장
      const changed = reindexed.filter(
        (e) => sorted.find((s) => s.id === e.id)!.order_index !== e.order_index,
      )
      await Promise.all(
        changed.map((e) => api.updateTimetable(t, e.id, { order_index: e.order_index })),
      )
      loadEntries()
    })
  }

  // ---------- 리워드 도감 ----------
  const [rewards, setRewards] = useState<Reward[]>([])
  const [nr, setNr] = useState({ name: '', total_count: '1', image_url: '', win_rate_pct: '10' })
  const [claimsMap, setClaimsMap] = useState<Record<number, RewardClaimDetail[]>>({})
  const [openClaimsId, setOpenClaimsId] = useState<number | null>(null)
  const [editRate, setEditRate] = useState<{ id: number; value: string } | null>(null)

  const loadRewards = useCallback(() => {
    if (seasonId == null) {
      setRewards([])
      return
    }
    api.rewards(t, seasonId).then(setRewards).catch(() => setRewards([]))
  }, [t, seasonId])
  useEffect(loadRewards, [loadRewards])

  const addReward = () =>
    run(async () => {
      if (seasonId == null) throw new ApiError(400, '먼저 시즌을 선택하세요.')
      if (!nr.name.trim()) throw new ApiError(400, '상품명을 입력하세요.')
      await api.createReward(t, seasonId, {
        name: nr.name.trim(),
        total_count: Number(nr.total_count) || 1,
        image_url: nr.image_url.trim() || null,
        win_rate_pct: Number(nr.win_rate_pct) || 0,
      })
      setNr({ name: '', total_count: '1', image_url: '', win_rate_pct: '10' })
      loadRewards()
    })

  const removeReward = (id: number) =>
    run(async () => {
      await api.deleteReward(t, id)
      loadRewards()
    })

  const saveRate = (id: number) =>
    run(async () => {
      await api.updateReward(t, id, { win_rate_pct: Number(editRate?.value) || 0 })
      setEditRate(null)
      loadRewards()
    })

  const toggleClaims = async (rewardId: number) => {
    if (openClaimsId === rewardId) {
      setOpenClaimsId(null)
      return
    }
    const claims = await api.rewardClaims(t, rewardId).catch(() => [])
    setClaimsMap((prev) => ({ ...prev, [rewardId]: claims }))
    setOpenClaimsId(rewardId)
  }

  const gameTitle = (id: number) => games.find((g) => g.id === id)?.title ?? `게임 #${id}`
  // 타임테이블 항목의 스코어보드 집계 단위: score_mode 오버라이드 우선, 없으면 게임 기본값
  const entryModeLabel = (en: TimetableEntry): string => {
    const mode =
      en.score_mode ?? (defaultScoreMode(String(en.game_id)) || 'team')
    return mode === 'individual' ? '개인전' : '팀전'
  }
  const teamName2 = (id: number | null) =>
    id == null ? '미배정' : teams.find((x) => x.id === id)?.name ?? `타 시즌 #${id}`
  const hiddenRoleOf = (userId: number) =>
    hiddenAssignments.find((a) => a.user_id === userId)?.role_id ?? ''

  useLiveEvent(
    [
      'team_membership_changed',
      'reward_catalog_changed',
      'reward_claimed',
      'reward_unclaimed',
      'score_recorded',
      'score_changed',
    ],
    (e) => {
      if (seasonId == null) return
      if (e.type === 'team_membership_changed' && e.season_id === seasonId) {
        loadMemberships()
        loadUserStatus()
        loadTeams()
      }
      if (e.type === 'reward_catalog_changed' && e.season_id === seasonId) {
        loadRewards()
      }
      if (e.type === 'reward_claimed' || e.type === 'reward_unclaimed') {
        loadRewards()
        if (openClaimsId != null) {
          api.rewardClaims(t, openClaimsId)
            .then((claims) => setClaimsMap((prev) => ({ ...prev, [openClaimsId]: claims })))
            .catch(() => {})
        }
      }
      if (e.type === 'score_recorded' || e.type === 'score_changed') {
        loadUserStatus()
      }
    },
  )

  return (
    <div className="page admin">
      <button className="back" onClick={onClose}>
        ← 닫기
      </button>
      <h2 className="detail-title">🛠 운영 관리</h2>
      {error && <p className="error">{error}</p>}

      {/* ① 시즌 */}
      <h3 className="sec-title">① 시즌</h3>
      <div className="op-row">
        <input
          placeholder="새 시즌 이름"
          value={seasonName}
          onChange={(e) => setSeasonName(e.target.value)}
        />
        <button className="op-btn" disabled={busy} onClick={createSeason}>
          생성
        </button>
      </div>
      <div className="admin-list">
        {seasons.map((s) => (
          <div key={s.id} className={`admin-row${s.id === seasonId ? ' sel' : ''}`}>
            {edit?.kind === 'season' && edit.id === s.id ? (
              <>
                <input value={editValue} onChange={(e) => setEditValue(e.target.value)} />
                <button className="mini-btn" disabled={busy} onClick={() => renameSeason(s.id)}>
                  저장
                </button>
                <button className="mini-btn ghost" onClick={() => setEdit(null)}>
                  취소
                </button>
              </>
            ) : (
              <>
                <button className="row-main" onClick={() => setSeasonId(s.id)}>
                  <b>{s.name}</b>
                  <span className={`chip ${s.status === 'active' ? 'state' : ''}`}>
                    {STATUS_LABEL[s.status] ?? s.status}
                  </span>
                </button>
                {s.status !== 'active' && (
                  <button className="mini-btn" disabled={busy} onClick={() => activateSeason(s.id)}>
                    활성화
                  </button>
                )}
                <button className="mini-btn ghost" onClick={() => startEdit('season', s.id, s.name)}>
                  수정
                </button>
                <button className="mini-btn danger" disabled={busy} onClick={() => deleteSeason(s.id)}>
                  삭제
                </button>
              </>
            )}
          </div>
        ))}
      </div>

      <div className="mini-tabs rank-tabs admin-tabs">
        {seasonId != null && (
          <>
            <button className={adminTab === 'teams' ? 'on' : 'off'} onClick={() => setAdminTab('teams')}>
              팀·유저
            </button>
            <button className={adminTab === 'timetable' ? 'on' : 'off'} onClick={() => setAdminTab('timetable')}>
              타임테이블
            </button>
            <button className={adminTab === 'rewards' ? 'on' : 'off'} onClick={() => setAdminTab('rewards')}>
              리워드
            </button>
            <button className={adminTab === 'users' ? 'on' : 'off'} onClick={() => setAdminTab('users')}>
              사용자 현황
            </button>
            <button className={adminTab === 'hidden' ? 'on' : 'off'} onClick={() => setAdminTab('hidden')}>
              개인 히든 롤
            </button>
            <button className={adminTab === 'buffs' ? 'on' : 'off'} onClick={() => setAdminTab('buffs')}>
              버프/디버프
            </button>
            <button className={adminTab === 'notices' ? 'on' : 'off'} onClick={() => setAdminTab('notices')}>
              공지
            </button>
            <button className={adminTab === 'quiz' ? 'on' : 'off'} onClick={() => setAdminTab('quiz')}>
              문제 데이터
            </button>
            <button className={adminTab === 'season' ? 'on' : 'off'} onClick={() => setAdminTab('season')}>
              시즌·뽑기
            </button>
          </>
        )}
        <button className={adminTab === 'reset' ? 'on' : 'off'} onClick={() => setAdminTab('reset')}>
          데이터 초기화
        </button>
      </div>

      {adminTab === 'reset' ? (
        <>
          <h3 className="sec-title">데이터 초기화</h3>
          <div className="reset-panel">
            <p className="danger-note">
              현재 DB의 모든 테이블을 초기화한 뒤 운영 데이터를 다시 넣습니다.
              사용자, 운영자, 팀, 게임 목록만 남고 타임테이블·세션·라운드·점수·공지·리워드는 비워집니다.
            </p>
            <label className="reset-confirm">
              <span>확인 문구</span>
              <input
                className="mini-input"
                value={resetConfirm}
                onChange={(e) => setResetConfirm(e.target.value)}
                placeholder="운영 데이터 초기화"
              />
            </label>
            <button
              className="op-btn danger"
              disabled={busy || resetConfirm !== '운영 데이터 초기화'}
              onClick={resetOperationalData}
            >
              데이터 초기화 후 운영 데이터 넣기
            </button>
            {resetMessage && <p className="muted">{resetMessage}</p>}
          </div>
        </>
      ) : seasonId == null ? (
        <p className="muted" style={{ marginTop: 16 }}>시즌을 먼저 선택/생성하세요.</p>
      ) : (
        <>
          {adminTab === 'notices' ? (
            <>
              <h3 className="sec-title">실시간 공지</h3>
              <div className="notice-admin-form">
                <textarea
                  className="mini-input notice-textarea"
                  placeholder="사용자에게 보여줄 공지 내용을 입력하세요."
                  value={noticeMessage}
                  onChange={(e) => setNoticeMessage(e.target.value)}
                  maxLength={500}
                />
                <div className="op-row">
                  <label className="notice-duration">
                    <span>유지 시간(분)</span>
                    <input
                      type="number"
                      min={1}
                      max={1440}
                      value={noticeDuration}
                      onChange={(e) => setNoticeDuration(e.target.value)}
                    />
                  </label>
                  <button className="op-btn" disabled={busy} onClick={createNotice}>
                    공지하기
                  </button>
                </div>
              </div>
              <div className="admin-list">
                {notices.length === 0 ? (
                  <p className="muted">등록된 공지가 없습니다.</p>
                ) : (
                  notices.map((notice) => (
                    <div key={notice.id} className="admin-row notice-admin-row">
                      <span className="row-main">
                        <b>{notice.message}</b>
                        <span className="muted">
                          만료 {new Date(notice.expires_at).toLocaleString('ko-KR')}
                        </span>
                      </span>
                      <button className="mini-btn danger" disabled={busy} onClick={() => deleteNotice(notice.id)}>
                        삭제
                      </button>
                    </div>
                  ))
                )}
              </div>
            </>
          ) : adminTab === 'quiz' ? (
            <>
              <h3 className="sec-title">문제 데이터 — 퀴즈 대결</h3>
              <p className="muted" style={{ margin: '0 0 10px' }}>
                준비된 객관식 문제를 <b>퀴즈 대결</b> 세션에 대기 라운드로 적재합니다.
                {quizCatalog && ` (총 ${quizCatalog.total}문제 · ${quizCatalog.categories.length}개 카테고리)`}
              </p>

              {/* 적재 옵션 */}
              <label className="quiz-opt">
                <input
                  type="checkbox"
                  checked={quizCreateSession}
                  onChange={(e) => setQuizCreateSession(e.target.checked)}
                />
                <span>세션이 없으면 새로 생성</span>
              </label>

              {/* 모드 버튼 + 설명 */}
              <div className="quiz-modes">
                <div className="quiz-mode-row all">
                  <button
                    className="op-btn"
                    disabled={busy || !quizCatalog}
                    onClick={() => seedQuiz({})}
                  >
                    전체 적재
                  </button>
                  <span className="muted">
                    모든 문제{quizCatalog ? ` ${quizCatalog.total}개` : ''}를 대기 라운드로 추가합니다.
                  </span>
                </div>

                <div className="quiz-mode-row random">
                  <button
                    className="op-btn"
                    disabled={busy}
                    onClick={() => seedQuiz({ limit: Number(quizLimit) || 1, shuffle: true })}
                  >
                    무작위 적재
                  </button>
                  <span className="muted">
                    무작위로 섞어
                    <input
                      className="quiz-limit"
                      type="number"
                      min={1}
                      value={quizLimit}
                      onChange={(e) => setQuizLimit(e.target.value)}
                    />
                    문제만 추가합니다.
                  </span>
                </div>

                <div className="quiz-mode-row category">
                  <button
                    className="op-btn"
                    disabled={busy || quizCats.length === 0}
                    onClick={() => seedQuiz({ categories: quizCats })}
                  >
                    카테고리 적재
                  </button>
                  <span className="muted">
                    아래에서 고른 카테고리 문제만 추가합니다. {quizCats.length > 0 && `(${quizCats.length}개 선택)`}
                  </span>
                </div>

                <div className="quiz-mode-row replace">
                  <button
                    className="op-btn"
                    disabled={busy || !quizCatalog}
                    onClick={() => {
                      if (confirm('기존 대기 라운드를 삭제하고 전체 문제를 다시 적재할까요?')) {
                        seedQuiz({ replace: true })
                      }
                    }}
                  >
                    교체 적재
                  </button>
                  <span className="muted">제출 기록 없는 기존 대기 라운드를 지운 뒤 전체를 다시 추가합니다.</span>
                </div>
              </div>

              {quizMessage && <p className="quiz-seed-msg">{quizMessage}</p>}

              {/* 카테고리 선택 */}
              <h3 className="sec-title">카테고리</h3>
              <div className="quiz-cat-list">
                {(quizCatalog?.categories ?? []).map((c) => (
                  <label key={c.name} className={`quiz-cat-chip${quizCats.includes(c.name) ? ' on' : ''}`}>
                    <input
                      type="checkbox"
                      checked={quizCats.includes(c.name)}
                      onChange={() => toggleQuizCat(c.name)}
                    />
                    <span>{c.name}</span>
                    <em>{c.count}</em>
                  </label>
                ))}
              </div>

              {/* 문제 목록 (카테고리별 펼치기) */}
              <h3 className="sec-title">문제 미리보기</h3>
              <div className="admin-list">
                {(quizCatalog?.categories ?? []).map((c) => {
                  const open = quizOpenCat === c.name
                  const qs = (quizCatalog?.questions ?? []).filter((q) => q.category === c.name)
                  return (
                    <div key={c.name} style={{ marginBottom: 4 }}>
                      <button
                        className="row-main quiz-cat-toggle"
                        onClick={() => setQuizOpenCat(open ? null : c.name)}
                      >
                        <b>{open ? '▼' : '▶'} {c.name}</b>
                        <span className="chip">{c.count}문제</span>
                      </button>
                      {open && (
                        <ol className="quiz-q-list">
                          {qs.map((q, i) => (
                            <li key={i} className="quiz-q-item">
                              <div className="quiz-q-prompt">{q.prompt}</div>
                              <div className="quiz-q-options">
                                {q.options.map((o, j) => (
                                  <span key={j} className={`quiz-q-opt${o === q.answer ? ' answer' : ''}`}>
                                    {o}
                                  </span>
                                ))}
                              </div>
                            </li>
                          ))}
                        </ol>
                      )}
                    </div>
                  )
                })}
              </div>
            </>
          ) : adminTab === 'users' ? (
            <>
              <h3 className="sec-title">사용자 현황</h3>
              <div className="admin-list">
                {userStatus.length === 0 ? (
                  <p className="muted">표시할 사용자가 없습니다.</p>
                ) : (
                  userStatus.map((u) => (
                    <div key={u.user_id} className="admin-row user-status-row">
                      <span className="row-main">
                        <b>{u.nickname}</b>
                        <span className={`chip ${u.role === 'admin' ? 'state' : ''}`}>
                          {u.role === 'admin' ? '운영자' : '사용자'}
                        </span>
                        <span className="muted">{u.team_name ?? '미배정'}</span>
                      </span>
                      <span className="status-score">누적 {u.cumulative_score}</span>
                      <span className="status-point">포인트 {u.point}</span>
                    </div>
                  ))
                )}
              </div>
            </>
          ) : adminTab === 'hidden' ? (
            <>
              <h3 className="sec-title">개인 히든 롤</h3>
              <div className="op-row" style={{ marginBottom: 8 }}>
                <input placeholder="히든롤 이름" value={newHiddenRole.name} onChange={(e) => setNewHiddenRole({ ...newHiddenRole, name: e.target.value })} />
                <input placeholder="설명" value={newHiddenRole.description} onChange={(e) => setNewHiddenRole({ ...newHiddenRole, description: e.target.value })} />
                <input placeholder="성공 조건" value={newHiddenRole.success_condition} onChange={(e) => setNewHiddenRole({ ...newHiddenRole, success_condition: e.target.value })} />
                <button className="op-btn" disabled={busy} onClick={createHiddenRole}>추가</button>
              </div>
              <div className="admin-list" style={{ marginBottom: 10 }}>
                {hiddenRoles.map((role) => (
                  <div key={role.id} className="admin-row">
                    <span className="row-main">
                      <b>{role.name}</b>
                      <span className="muted">{role.description}</span>
                    </span>
                    <button className="mini-btn danger" disabled={busy} onClick={() => run(async () => { await api.deleteHiddenRole(t, role.id); loadHiddenRoles(); loadHiddenAssignments() })}>삭제</button>
                  </div>
                ))}
              </div>
              <h3 className="sec-title">팀원별 배정</h3>
              <div className="admin-list">
                {users.map((u) => (
                  <div key={u.id} className="admin-row">
                    <span className="row-main">
                      <b>{u.nickname}</b>
                      <span className="muted">{teamName2(teamOf(u.id))}</span>
                    </span>
                    <select className="assign" value={hiddenRoleOf(u.id)} disabled={busy} onChange={(e) => assignHiddenRole(u.id, e.target.value)}>
                      <option value="">미배정</option>
                      {hiddenRoles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
                    </select>
                  </div>
                ))}
              </div>
            </>
          ) : adminTab === 'buffs' ? (
            <>
              <h3 className="sec-title">버프/디버프 카탈로그</h3>
              <div className="op-row" style={{ marginBottom: 8 }}>
                <input placeholder="이름" value={newBuff.name} onChange={(e) => setNewBuff({ ...newBuff, name: e.target.value })} />
                <input placeholder="설명" value={newBuff.description} onChange={(e) => setNewBuff({ ...newBuff, description: e.target.value })} />
                <select value={newBuff.type} onChange={(e) => setNewBuff({ ...newBuff, type: e.target.value as 'buff' | 'debuff' })}>
                  <option value="buff">버프</option>
                  <option value="debuff">디버프</option>
                </select>
                <button className="op-btn" disabled={busy} onClick={createBuff}>추가</button>
              </div>
              <div className="admin-list" style={{ marginBottom: 10 }}>
                {buffs.map((buff) => (
                  <div key={buff.id} className="admin-row">
                    <span className="row-main">
                      <b>{buff.type === 'buff' ? '버프' : '디버프'} · {buff.name}</b>
                      <span className="muted">{buff.description}</span>
                    </span>
                    <button className="mini-btn danger" disabled={busy} onClick={() => run(async () => { await api.deleteBuff(t, buff.id); loadBuffs(); loadTeamBuffs() })}>삭제</button>
                  </div>
                ))}
              </div>
              <h3 className="sec-title">게임별 팀 부여</h3>
              <div className="admin-list">
                {sortedEntries.map((entry) => {
                  const session = entrySessions[entry.id]
                  return (
                    <TeamBuffAssignRow
                      key={entry.id}
                      entryId={entry.id}
                      title={entry.label ?? gameTitle(entry.game_id)}
                      hasSession={!!session}
                      teams={teams}
                      buffs={buffs}
                      busy={busy}
                      onAssign={assignTeamBuff}
                    />
                  )
                })}
              </div>
              <h3 className="sec-title">부여 현황</h3>
              <div className="admin-list">
                {teamBuffs.map((item) => (
                  <div key={item.id} className="admin-row">
                    <span className="row-main">
                      <b>{item.team_name} · {item.buff_name}</b>
                      <span className="muted">세션 #{item.session_id} · {item.session_state}</span>
                    </span>
                    <button className="mini-btn danger" disabled={busy} onClick={() => run(async () => { await api.deleteTeamBuff(t, item.id); loadTeamBuffs() })}>삭제</button>
                  </div>
                ))}
              </div>
            </>
          ) : adminTab === 'teams' ? (
            <>
          {/* 팀 */}
          <h3 className="sec-title">팀 (선택 시즌)</h3>
          <div className="op-row">
            <input
              placeholder="새 팀 이름 (예: 🔴 레드팀)"
              value={teamName}
              onChange={(e) => setTeamName(e.target.value)}
            />
            <button className="op-btn" disabled={busy} onClick={createTeam}>
              생성
            </button>
          </div>
          <div className="admin-list">
            {teams.length === 0 ? (
              <p className="muted">아직 팀이 없습니다.</p>
            ) : (
              teams.map((tm) => (
                <div key={tm.id} className="admin-row">
                  {edit?.kind === 'team' && edit.id === tm.id ? (
                    <>
                      <input value={editValue} onChange={(e) => setEditValue(e.target.value)} />
                      <button className="mini-btn" disabled={busy} onClick={() => renameTeam(tm.id)}>
                        저장
                      </button>
                      <button className="mini-btn ghost" onClick={() => setEdit(null)}>
                        취소
                      </button>
                    </>
                  ) : (
                    <>
                      <span className="row-main">
                        <b>{tm.name}</b>
                        <span className="chip">
                          {memberships.filter((m) => m.team_id === tm.id).length}명
                        </span>
                      </span>
                      <button className="mini-btn ghost" onClick={() => startEdit('team', tm.id, tm.name)}>
                        수정
                      </button>
                      <button className="mini-btn danger" disabled={busy} onClick={() => deleteTeam(tm.id)}>
                        삭제
                      </button>
                    </>
                  )}
                </div>
              ))
            )}
          </div>

          {/* ③ 유저 배치 */}
          <h3 className="sec-title">③ 유저 배치</h3>
          <div className="op-row" style={{ marginBottom: 10 }}>
            <input
              placeholder="아이디"
              value={nu.username}
              onChange={(e) => setNu({ ...nu, username: e.target.value })}
            />
            <input
              placeholder="닉네임"
              value={nu.nickname}
              onChange={(e) => setNu({ ...nu, nickname: e.target.value })}
            />
            <input
              placeholder="비밀번호"
              value={nu.password}
              onChange={(e) => setNu({ ...nu, password: e.target.value })}
            />
            <button className="op-btn" disabled={busy} onClick={createUser}>
              참가자 추가
            </button>
          </div>
          <div className="admin-list">
            {users.map((u) => (
              <div key={u.id} className="admin-row">
                <span className="row-main">
                  <b>{u.nickname}</b>
                  <span className="muted">@{u.username}</span>
                  {u.role === 'admin' && <span className="chip state">운영자</span>}
                  <span className="muted" style={{ marginLeft: 'auto' }}>
                    {teamName2(teamOf(u.id))}
                  </span>
                </span>
                <select
                  className="assign"
                  value={teamOf(u.id) ?? ''}
                  disabled={busy}
                  onChange={(e) => assign(u.id, e.target.value)}
                >
                  <option value="">미배정</option>
                  {teams.map((tm) => (
                    <option key={tm.id} value={tm.id}>
                      {tm.name}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>

            </>
          ) : adminTab === 'timetable' ? (
            <>
          {/* 타임테이블 */}
          <h3 className="sec-title">타임테이블</h3>
          <div className="op-row tt-add-row">
            <select value={pickGame} onChange={(e) => onPickGame(e.target.value)}>
              <option value="">게임 선택</option>
              {games.filter((g) => g.input_type !== 'tap').map((g) => (
                <option key={g.id} value={g.id}>
                  {g.title}
                </option>
              ))}
            </select>
            <input
              placeholder="게임 이름 (예: 오프라인 게임 2)"
              value={pickLabel}
              onChange={(e) => setPickLabel(e.target.value)}
            />
            <select
              value={pickScoreMode}
              onChange={(e) => setPickScoreMode(e.target.value as '' | 'team' | 'individual')}
            >
              <option value="">게임 기본</option>
              <option value="team">팀전 (팀별 점수)</option>
              <option value="individual">개인전 (개인별 점수)</option>
            </select>
            <button className="op-btn" disabled={busy} onClick={addEntry}>
              추가
            </button>
          </div>
          {entries.length === 0 ? (
            <div className="admin-list">
              <p className="muted">등록된 게임이 없습니다.</p>
            </div>
          ) : (
            <>
              <p className="muted" style={{ margin: '0 0 6px' }}>
                ⠿ 핸들을 잡고 드래그해 진행 순서를 바꿀 수 있어요.
              </p>
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
                <SortableContext
                  items={sortedEntries.map((en) => en.id)}
                  strategy={verticalListSortingStrategy}
                >
                  <div className="admin-list">
                    {sortedEntries.map((en) => (
                      <SortableEntryRow
                        key={en.id}
                        id={en.id}
                        order={en.order_index}
                        title={en.label ?? gameTitle(en.game_id)}
                        modeLabel={entryModeLabel(en)}
                        mainVisible={en.main_visible}
                        busy={busy}
                        onToggleVisible={toggleEntryVisible}
                        onDelete={deleteEntry}
                      />
                    ))}
                  </div>
                </SortableContext>
              </DndContext>
            </>
          )}

            </>
          ) : adminTab === 'rewards' ? (
            <>
          {/* 리워드 도감 */}
          <h3 className="sec-title">리워드 도감</h3>
          <div className="op-row" style={{ marginBottom: 6 }}>
            <input
              placeholder="상품명"
              value={nr.name}
              onChange={(e) => setNr({ ...nr, name: e.target.value })}
            />
            <input
              className="op-score"
              type="number"
              placeholder="수량"
              min={1}
              value={nr.total_count}
              onChange={(e) => setNr({ ...nr, total_count: e.target.value })}
            />
            <input
              className="op-score"
              type="number"
              placeholder="확률(%)"
              min={0}
              max={100}
              value={nr.win_rate_pct}
              onChange={(e) => setNr({ ...nr, win_rate_pct: e.target.value })}
            />
            <button className="op-btn" disabled={busy} onClick={addReward}>
              추가
            </button>
          </div>
          <div className="op-row" style={{ marginBottom: 10 }}>
            <input
              placeholder="이미지 URL (선택)"
              value={nr.image_url}
              onChange={(e) => setNr({ ...nr, image_url: e.target.value })}
            />
          </div>
          <div className="admin-list">
            {rewards.map((r) => (
              <div key={r.id} style={{ marginBottom: 4 }}>
                <div className="admin-row">
                  <span className="row-main">
                    <b>{r.is_revealed ? '🎁' : '❓'} {r.name}</b>
                    <span className="chip">{r.total_count}개</span>
                    <span className="chip">{Math.round((r.win_rate ?? 0) * 100)}%</span>
                  </span>
                  <button className="mini-btn ghost" onClick={() => setEditRate(editRate?.id === r.id ? null : { id: r.id, value: String(Math.round((r.win_rate ?? 0) * 100)) })}>
                    확률
                  </button>
                  <button className="mini-btn" onClick={() => toggleClaims(r.id)}>
                    당첨자 {openClaimsId === r.id ? '▲' : '▼'}
                  </button>
                  <button className="mini-btn danger" disabled={busy} onClick={() => removeReward(r.id)}>
                    삭제
                  </button>
                </div>
                {editRate?.id === r.id && (
                  <div className="op-row" style={{ padding: '6px 12px', background: '#f0f4ff', borderRadius: 8, marginTop: 2, gap: 6 }}>
                    <span className="muted" style={{ fontSize: 13 }}>당첨 확률</span>
                    <input
                      className="op-score"
                      type="number"
                      min={0}
                      max={100}
                      value={editRate.value}
                      onChange={(e) => setEditRate({ id: r.id, value: e.target.value })}
                      style={{ width: 70 }}
                    />
                    <span className="muted">%</span>
                    <button className="mini-btn" disabled={busy} onClick={() => saveRate(r.id)}>저장</button>
                    <button className="mini-btn ghost" onClick={() => setEditRate(null)}>취소</button>
                  </div>
                )}
                {openClaimsId === r.id && (
                  <div style={{ padding: '6px 12px', background: '#f8f9fb', borderRadius: 8, marginTop: 2, fontSize: 13 }}>
                    {(claimsMap[r.id] ?? []).length === 0 ? (
                      <p className="muted" style={{ margin: 0 }}>아직 당첨자가 없습니다.</p>
                    ) : (
                      (claimsMap[r.id] ?? []).map((c) => (
                        <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
                          <span>🎉 {c.nickname}</span>
                          <span className="muted">{new Date(c.claimed_at).toLocaleString('ko-KR')}</span>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
            </>
          ) : (
            <>
              <h3 className="sec-title">뽑기 설정</h3>
              <div className="op-row" style={{ marginBottom: 12 }}>
                <span className="muted" style={{ fontSize: 13 }}>1회 차감 포인트</span>
                <input
                  className="op-score"
                  type="number"
                  min={1}
                  value={gachaCost}
                  onChange={(e) => setGachaCost(e.target.value)}
                />
                <button className="op-btn" disabled={busy} onClick={saveGachaCost}>
                  저장
                </button>
              </div>
            </>
          )}
        </>
      )}
      </div>
    )
  }
