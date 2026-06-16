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
  type Reward,
  type RewardClaimDetail,
  type SeasonMembership,
  type Team,
  type TimetableEntry,
  type UserProfile,
} from '../api'
import { useAuth } from '../auth'
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
  busy,
  onDelete,
}: {
  id: number
  order: number
  title: string
  busy: boolean
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
      </span>
      <button className="mini-btn danger" disabled={busy} onClick={() => onDelete(id)}>
        삭제
      </button>
    </div>
  )
}

export default function AdminPage({ onClose }: Props) {
  const { token } = useAuth()
  const t = token as string
  const { seasons, seasonId, setSeasonId, refresh: refreshSeasons } = useSeason()

  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

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
    })

  // ---------- 타임테이블 ----------
  const [entries, setEntries] = useState<TimetableEntry[]>([])
  const [games, setGames] = useState<Game[]>([])
  const [pickGame, setPickGame] = useState('')
  // 클릭(작은 움직임)은 드래그로 오인하지 않도록 8px 이동 후 드래그 시작
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  )

  const loadEntries = useCallback(() => {
    if (seasonId == null) {
      setEntries([])
      return
    }
    api.timetable(t, seasonId).then(setEntries).catch(() => setEntries([]))
  }, [t, seasonId])
  useEffect(loadEntries, [loadEntries])
  useEffect(() => {
    api.games(t).then(setGames).catch(() => setGames([]))
  }, [t])
  const sortedEntries = entries.slice().sort((a, b) => a.order_index - b.order_index)

  const addEntry = () =>
    run(async () => {
      if (seasonId == null) throw new ApiError(400, '먼저 시즌을 선택하세요.')
      if (!pickGame) throw new ApiError(400, '게임을 선택하세요.')
      const game = games.find((g) => g.id === Number(pickGame))
      await api.createTimetable(t, seasonId, {
        game_id: Number(pickGame),
        order_index: entries.length + 1,
        label: game ? game.title : null,
      })
      setPickGame('')
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
  const teamName2 = (id: number | null) =>
    id == null ? '미배정' : teams.find((x) => x.id === id)?.name ?? `타 시즌 #${id}`

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

      {seasonId == null ? (
        <p className="muted" style={{ marginTop: 16 }}>시즌을 먼저 선택/생성하세요.</p>
      ) : (
        <>
          {/* ② 팀 */}
          <h3 className="sec-title">② 팀 (선택 시즌)</h3>
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

          {/* ④ 타임테이블 */}
          <h3 className="sec-title">④ 타임테이블</h3>
          <div className="op-row">
            <select value={pickGame} onChange={(e) => setPickGame(e.target.value)}>
              <option value="">게임 선택</option>
              {games.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.title}
                </option>
              ))}
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
                        busy={busy}
                        onDelete={deleteEntry}
                      />
                    ))}
                  </div>
                </SortableContext>
              </DndContext>
            </>
          )}

          {/* ⑤ 리워드 도감 */}
          <h3 className="sec-title">⑤ 리워드 도감</h3>
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
      )}
    </div>
  )
}
