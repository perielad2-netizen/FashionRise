import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { preloadDefaultFabricTiles } from '@/lib/defaultFabricTiles'
import { bindFabricCacheToUser } from '@/lib/fabricAssetCache'
import {
  fetchMe,
  getGoogleOAuthStatus,
  getRegistrationStatus,
  login as apiLogin,
  logoutLocal,
  register as apiRegister,
  restoreSession,
  type LoginPayload,
  type RegisterPayload,
  type RegisterResult,
  type RegistrationStatus,
  type User,
} from '@/services/auth/authApi'
import { tokenStore } from '@/services/auth/tokenStore'
import { isNativeIosStarsShop, recoverPendingStarsPurchases } from '@/services/native/iap'
import { isNativeShell, nativePlatform } from '@/services/native/platform'

type AuthState = {
  user: User | null
  bootstrapping: boolean
  login: (payload: LoginPayload) => Promise<void>
  register: (payload: RegisterPayload) => Promise<RegisterResult>
  logout: () => void
  refreshUser: () => Promise<void>
  isAuthenticated: boolean
  googleOAuthAvailable: boolean
  registrationStatus: RegistrationStatus | null
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [bootstrapping, setBootstrapping] = useState(true)
  const [googleOAuthAvailable, setGoogleOAuthAvailable] = useState(false)
  const [registrationStatus, setRegistrationStatus] = useState<RegistrationStatus | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const loadPublicStatus = async () => {
        try {
          const [google, registration] = await Promise.all([
            getGoogleOAuthStatus().catch(() => null),
            getRegistrationStatus().catch(() => null),
          ])
          if (cancelled) return
          // Guideline 4.8: hide Google Sign-In in the iOS native shell; keep it on web.
          const googleOn =
            Boolean(google?.google_oauth_enabled) &&
            !(isNativeShell() && nativePlatform() === 'ios')
          setGoogleOAuthAvailable(googleOn)
          if (registration) setRegistrationStatus(registration)
        } catch {
          /* status unavailable — password login still works */
        }
      }

      if (tokenStore.get()) {
        const restored = await restoreSession()
        if (!cancelled) {
          setUser(restored)
          setBootstrapping(false)
        }
        // Still load public capability so logout → login shows Create Account correctly.
        void loadPublicStatus()
        return
      }
      await loadPublicStatus()
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
    if (result.status === 'authenticated') {
      bindFabricCacheToUser(result.user.id)
      setUser(result.user)
    }
    return result
  }, [])

  const logout = useCallback(() => {
    logoutLocal()
    bindFabricCacheToUser(null)
    setUser(null)
  }, [])

  const refreshUser = useCallback(async () => {
    const tokenAtStart = tokenStore.get()
    if (!tokenAtStart) return
    try {
      const me = await fetchMe()
      // Drop stale /me after logout or account switch — never paint another user's wallet.
      // Compare token *values* (tokenStore.get() allocates a fresh object each call).
      const tokenNow = tokenStore.get()
      if (
        !tokenNow ||
        tokenNow.accessToken !== tokenAtStart.accessToken ||
        tokenNow.refreshToken !== tokenAtStart.refreshToken
      ) {
        return
      }
      bindFabricCacheToUser(me.id)
      setUser(me)
    } catch {
      /* keep existing session identity on transient /me failures */
    }
  }, [])

  useEffect(() => {
    bindFabricCacheToUser(user?.id ?? null)
    // Shared AI default tiles are public; warm them once a session is alive.
    if (user?.id) void preloadDefaultFabricTiles()
  }, [user?.id])

  // After sign-in, attempt bounded Apple unfinished-txn recovery for this account only.
  // Account switches clear user first (login/register), so prior recovery cannot credit the new session.
  useEffect(() => {
    if (!user?.id || bootstrapping || !isNativeIosStarsShop()) return
    let cancelled = false
    void recoverPendingStarsPurchases()
      .then((out) => {
        if (cancelled || out.recovered <= 0) return
        return fetchMe().then((me) => {
          if (!cancelled) setUser(me)
        })
      })
      .catch(() => {
        /* recovery is best-effort */
      })
    return () => {
      cancelled = true
    }
  }, [user?.id, bootstrapping])

  const value = useMemo<AuthState>(
    () => ({
      user,
      bootstrapping,
      login,
      register,
      logout,
      refreshUser,
      isAuthenticated: Boolean(user),
      googleOAuthAvailable,
      registrationStatus,
    }),
    [
      user,
      bootstrapping,
      login,
      register,
      logout,
      refreshUser,
      googleOAuthAvailable,
      registrationStatus,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
