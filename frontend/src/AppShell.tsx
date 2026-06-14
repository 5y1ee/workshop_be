import { useState } from 'react'
import { useAuth } from './auth'
import { useSeason } from './season'
import { useLive } from './live'
import MyPage from './pages/MyPage'
import RankingPage from './pages/RankingPage'
import MainPage from './pages/MainPage'
import DexPage from './pages/DexPage'
import MiniGamePage from './pages/MiniGamePage'

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

  return (
    <div className="shell">
      <header className="shell-top">
        <span className="shell-greet">👋 {user?.nickname}</span>
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
        <button className="link" onClick={logout}>
          나가기
        </button>
      </header>

      <main className="shell-main">
        {loading ? (
          <p className="muted" style={{ padding: 20 }}>
            시즌 불러오는 중…
          </p>
        ) : seasonId == null ? (
          <p className="muted" style={{ padding: 20 }}>
            시즌이 없습니다. 운영자에게 문의하세요.
          </p>
        ) : (
          <>
            {tab === 'my' && <MyPage />}
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
            className={`tab${tab === t.key ? ' active' : ''}${t.center ? ' center' : ''}`}
            onClick={() => setTab(t.key)}
          >
            <span className="ic">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </nav>
    </div>
  )
}
