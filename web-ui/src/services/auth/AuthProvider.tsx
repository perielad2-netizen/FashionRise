import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { bindFabricCacheToUser } from '@/lib/fabricAssetCache'
import {
  getGoogleOAuthStatus,
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
  googleOAuthAvailable: boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [bootstrapping, setBootstrapping] = useState(true)
  const [googleOAuthAvailable, setGoogleOAuthAvailable] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (tokenStore.get()) {
        const restored = await restoreSession()
        if (!cancelled) {
          setUser(restored)
          setBootstrapping(false)
        }
        return
      }
      try {
        const status = await getGoogleOAuthStatus()
        if (!cancelled) setGoogleOAuthAvailable(Boolean(status.google_oauth_enabled))
      } catch {
        /* status unavailable — password / register still work */
      }
      if (!cancelled) setBootstrapping(false)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (payload: LoginPayload) => {
    setUser(null)
    bindFabricCacheToUser(null)
    const result = await apiLogin(payload)
    bindFabricCacheToUser(result.user.id)
    setUser(result.user)
  }, [])

  const register = useCallback(async (payload: RegisterPayload) => {
    setUser(null)
    bindFabricCacheToUser(null)
    const result = await apiRegister(payload)
    bindFabricCacheToUser(result.user.id)
    setUser(result.user)
  }, [])

  const logout = useCallback(() => {
    logoutLocal()
    bindFabricCacheToUser(null)
    setUser(null)
  }, [])

  useEffect(() => {
    bindFabricCacheToUser(user?.id ?? null)
  }, [user?.id])

  const value = useMemo<AuthState>(
    () => ({
      user,
      bootstrapping,
      login,
      register,
      logout,
      isAuthenticated: Boolean(user),
      googleOAuthAvailable,
    }),
    [user, bootstrapping, login, register, logout, googleOAuthAvailable],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
