import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  login as apiLogin,
  logoutLocal,
  restoreSession,
  type LoginPayload,
  type User,
} from '@/services/auth/authApi'
import { tokenStore } from '@/services/auth/tokenStore'

type AuthState = {
  user: User | null
  bootstrapping: boolean
  login: (payload: LoginPayload) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [bootstrapping, setBootstrapping] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (!tokenStore.get()) {
        if (!cancelled) setBootstrapping(false)
        return
      }
      const restored = await restoreSession()
      if (!cancelled) {
        setUser(restored)
        setBootstrapping(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (payload: LoginPayload) => {
    const result = await apiLogin(payload)
    setUser(result.user)
  }, [])

  const logout = useCallback(() => {
    logoutLocal()
    setUser(null)
  }, [])

  const value = useMemo<AuthState>(
    () => ({
      user,
      bootstrapping,
      login,
      logout,
      isAuthenticated: Boolean(user),
    }),
    [user, bootstrapping, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
