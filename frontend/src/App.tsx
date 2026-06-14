import { useAuth } from './auth'
import { SeasonProvider } from './season'
import { LiveProvider } from './live'
import LoginPage from './pages/LoginPage'
import AppShell from './AppShell'

export default function App() {
  const { token } = useAuth()
  if (!token) {
    return (
      <div className="container">
        <LoginPage />
      </div>
    )
  }
  return (
    <div className="container">
      <LiveProvider>
        <SeasonProvider>
          <AppShell />
        </SeasonProvider>
      </LiveProvider>
    </div>
  )
}
