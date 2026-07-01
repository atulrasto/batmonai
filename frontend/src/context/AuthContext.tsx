import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react'
import type { User } from '../types'
import { me } from '../api/auth'

interface AuthState {
  user: User | null
  token: string | null
  loading: boolean
  setToken: (token: string) => void
  logout: () => void
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => localStorage.getItem('token'))
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    const t = localStorage.getItem('token')
    if (!t) { setUser(null); setLoading(false); return }
    try {
      const u = await me()
      setUser(u)
    } catch {
      localStorage.removeItem('token')
      setTokenState(null)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const setToken = useCallback((t: string) => {
    localStorage.setItem('token', t)
    setTokenState(t)
    refresh()
  }, [refresh])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    setTokenState(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, token, loading, setToken, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}
