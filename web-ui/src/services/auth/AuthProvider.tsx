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
  register as apiRegister,
  restoreSession,
  type LoginPayload,
  type RegisterPayload,
  type User,
} from '@/services/auth/authApi'
import { tokenStore } from '@/services/auth/tokenStore'

type AuthState = {
  user: User | null
  bootstrapping: boolean
  login: (payload: LoginPayload) => Promise<void>
  register: (payload: RegisterPayload) => Promise<void>
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
    // Drop any prior in-memory identity before applying the new session.
    setUser(null)
    const result = await apiLogin(payload)
    setUser(result.user)
  }, [])

  const register = useCallback(async (payload: RegisterPayload) => {
    setUser(null)
    const result = await apiRegister(payload)
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
      register,
      logout,
      isAuthenticated: Boolean(user),
    }),
    [user, bootstrapping, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
