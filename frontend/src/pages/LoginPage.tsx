import { useState, type FormEvent } from 'react'
import { api, ApiError } from '../api'
import { useAuth } from '../auth'

export default function LoginPage() {
  const { setSession } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      setSession(await api.login(username, password))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '로그인에 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page login">
      <form onSubmit={submit} className="card">
        <label>
          아이디
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoCapitalize="none"
            autoCorrect="off"
            placeholder="username"
          />
        </label>
        <label>
          비밀번호
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••"
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button disabled={loading || !username || !password}>
          {loading ? '로그인 중…' : '로그인'}
        </button>
      </form>
    </div>
  )
}
