import { useState } from 'react'
import { useAuth } from './auth'
import { useSeason } from './season'
import { useLive } from './live'
import MyPage from './pages/MyPage'
import RankingPage from './pages/RankingPage'
import MainPage from './pages/MainPage'
import DexPage from './pages/DexPage'
import MiniGamePage from './pages/MiniGamePage'
import AdminPage from './pages/AdminPage'
import SpeakingEventOverlay from './components/SpeakingEventOverlay'
import NoticeBanner from './components/NoticeBanner'

type Tab = 'my' | 'ranking' | 'main' | 'dex' | 'mini'

const TABS: { key: Tab; icon: string; label: string; center?: boolean }[] = [
  { key: 'my', icon: '🧢', label: '마이' },
  { key: 'ranking', icon: '🏆', label: '랭킹' },
  { key: 'main', icon: '⚡', label: '메인', center: true },
  { key: 'dex', icon: '📕', label: '도감' },
  { key: 'mini', icon: '🎲', label: '미니' },
]

export default function AppShell() {
  const { user, logout } = useAuth()
  const { seasons, seasonId, setSeasonId, loading } = useSeason()
  const { connected } = useLive()
  const [tab, setTab] = useState<Tab>('main')
  const [adminOpen, setAdminOpen] = useState(false)
  const isAdmin = user?.role === 'admin'

  return (
    <div className="shell">
      <header className="shell-top">
        <span className="shell-greet">🧢 {user?.nickname}</span>
        <select
          className="season-switch"
          value={seasonId ?? ''}
          onChange={(e) => setSeasonId(Number(e.target.value))}
        >
          {seasons.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <span className={connected ? 'live on' : 'live off'}>{connected ? '● LIVE' : '○'}</span>
        {isAdmin && (
          <button className="link" onClick={() => setAdminOpen(true)} title="운영 관리">
            ⚙️
          </button>
        )}
        <button className="link" onClick={logout}>
          나가기
        </button>
      </header>

      <main className="shell-main">
        <NoticeBanner />
        {adminOpen && isAdmin ? (
          <AdminPage onClose={() => setAdminOpen(false)} />
        ) : loading ? (
          <p className="muted" style={{ padding: 20 }}>
            시즌 불러오는 중…
          </p>
        ) : seasonId == null ? (
          <p className="muted" style={{ padding: 20 }}>
            {isAdmin
              ? '시즌이 없습니다. 우측 상단 ⚙️ 에서 시즌을 만드세요.'
              : '시즌이 없습니다. 운영자에게 문의하세요.'}
          </p>
        ) : (
          <>
            {tab === 'my' && <MyPage onBack={() => setTab('main')} />}
            {tab === 'ranking' && <RankingPage />}
            {tab === 'main' && <MainPage />}
            {tab === 'dex' && <DexPage />}
            {tab === 'mini' && <MiniGamePage />}
          </>
        )}
      </main>

      <nav className="nav">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`tab${tab === t.key && !adminOpen ? ' active' : ''}${t.center ? ' center' : ''}`}
            onClick={() => {
              setTab(t.key)
              setAdminOpen(false)
            }}
          >
            <span className="ic">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </nav>
      <SpeakingEventOverlay />
    </div>
  )
}
