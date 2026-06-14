import { createContext, useContext, useState, type ReactNode } from 'react'
import type { LoginResponse } from './api'

type SessionUser = Pick<LoginResponse, 'user_id' | 'nickname' | 'role' | 'team_id'>

interface AuthState {
  token: string | null
  user: SessionUser | null
  setSession: (res: LoginResponse) => void
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)
const STORAGE_KEY = 'workshop_auth'

interface Stored {
  token: string
  user: SessionUser
}

function load(): Stored | null {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as Stored
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const initial = load()
  const [token, setToken] = useState<string | null>(initial?.token ?? null)
  const [user, setUser] = useState<SessionUser | null>(initial?.user ?? null)

  const setSession = (res: LoginResponse) => {
    const u: SessionUser = {
      user_id: res.user_id,
      nickname: res.nickname,
      role: res.role,
      team_id: res.team_id,
    }
    setToken(res.access_token)
    setUser(u)
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ token: res.access_token, user: u }),
    )
  }

  const logout = () => {
    setToken(null)
    setUser(null)
    localStorage.removeItem(STORAGE_KEY)
  }

  return (
    <AuthContext.Provider value={{ token, user, setSession, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
