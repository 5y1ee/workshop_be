import { useAuth } from './auth'
import LoginPage from './pages/LoginPage'
import ScoreboardPage from './pages/ScoreboardPage'

export default function App() {
  const { token } = useAuth()
  return <div className="phone">{token ? <ScoreboardPage /> : <LoginPage />}</div>
}
