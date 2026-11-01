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
  getCfAccessSsoStatus,
  login as apiLogin,
  loginWithCloudflareAccess,
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
  loginWithAccess?: () => Promise<boolean>
  register: (payload: RegisterPayload) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
  accessSsoAvailable: boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [bootstrapping, setBootstrapping] = useState(true)
  const [accessSsoAvailable, setAccessSsoAvailable] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      // Existing FashionRise session first.
      if (tokenStore.get()) {
        const restored = await restoreSession()
        if (!cancelled) {
          setUser(restored)
          setBootstrapping(false)
        }
        return
      }
      // Optional seamless Cloudflare Access login (feature-flagged on the server).
      try {
        const status = await getCfAccessSsoStatus()
        if (!cancelled) setAccessSsoAvailable(Boolean(status.sso_enabled))
        if (status.sso_enabled) {
          try {
            const result = await loginWithCloudflareAccess()
            if (!cancelled) {
              bindFabricCacheToUser(result.user.id)
              setUser(result.user)
              setBootstrapping(false)
              return
            }
          } catch {
            // Keep password login — Access verification failed or email not linked.
          }
        }
      } catch {
        /* status endpoint unavailable — fall through to password login */
      }
      if (!cancelled) setBootstrapping(false)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (payload: LoginPayload) => {
    // Drop any prior in-memory identity before applying the new session.
    setUser(null)
    bindFabricCacheToUser(null)
    const result = await apiLogin(payload)
    bindFabricCacheToUser(result.user.id)
    setUser(result.user)
  }, [])

  const loginWithAccess = useCallback(async () => {
    try {
      setUser(null)
      bindFabricCacheToUser(null)
      const result = await loginWithCloudflareAccess()
      bindFabricCacheToUser(result.user.id)
      setUser(result.user)
      return true
    } catch {
      return false
    }
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

  // Keep fabric caches scoped to the restored / current user (covers session restore).
  useEffect(() => {
    bindFabricCacheToUser(user?.id ?? null)
  }, [user?.id])

  const value = useMemo<AuthState>(
    () => ({
      user,
      bootstrapping,
      login,
      loginWithAccess,
      register,
      logout,
      isAuthenticated: Boolean(user),
      accessSsoAvailable,
    }),
    [user, bootstrapping, login, loginWithAccess, register, logout, accessSsoAvailable],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
