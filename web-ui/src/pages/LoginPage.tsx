import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { UI_ASSETS } from '@/assets/uiAssets'
import { canAdvertiseRegistration } from '@/config/registrationUi'
import { validateLogin, type LoginFieldErrors } from '@/lib/validateLogin'
import { ApiError } from '@/services/api/client'
import { getGoogleOAuthStartUrl } from '@/services/auth/authApi'
import { useAuth } from '@/services/auth/AuthProvider'
import { openAndroidGoogleOAuth } from '@/services/native/googleOAuthReturn'
import { isNativeShell, nativePlatform } from '@/services/native/platform'
import { sanitizePushDestination } from '@/services/native/pushDestination'
import { peekPendingNotificationDestination } from '@/services/native/notificationNavigation'
import styles from './LoginPage.module.css'

function safePostLoginPath(candidate: unknown): string {
  if (typeof candidate !== 'string' || !candidate.trim()) return '/studio/home'
  const raw = candidate.trim()
  // Push destinations (and other studio deep links) — never auth/token routes.
  if (raw.startsWith('/studio') || raw.startsWith('/privacy')) {
    // Reuse push sanitizer for studio query allowlist; plain /studio/home stays.
    if (raw === '/studio/home' || raw.startsWith('/studio/home?')) return '/studio/home'
    if (raw.startsWith('/studio/fashionrise') || raw.startsWith('/studio/runway')) {
      return sanitizePushDestination(raw)
    }
    if (raw.startsWith('/studio/') && !raw.includes('?') && !raw.includes('#')) return raw
  }
  return '/studio/home'
}

export function LoginPage() {
  const {
    login,
    isAuthenticated,
    bootstrapping,
    googleOAuthAvailable,
    registrationStatus,
    passwordResetAvailable,
  } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<LoginFieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const showCreateAccount = canAdvertiseRegistration(
    registrationStatus?.registration_available ?? null,
  )

  const postLoginPath = useMemo(() => {
    const fromState = (location.state as { from?: string } | null)?.from
    const pending = peekPendingNotificationDestination()
    // Prefer an explicit protected-route return, then a queued push destination.
    return safePostLoginPath(fromState || pending || '/studio/home')
  }, [location.state])

  useEffect(() => {
    const err = searchParams.get('error')
    if (err) setFormError(err)
  }, [searchParams])

  if (bootstrapping) return null
  if (isAuthenticated) return <Navigate to={postLoginPath} replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (busy) return

    setFormError(null)
    const validated = validateLogin(email, password)
    if (!validated.ok) {
      setFieldErrors(validated.errors)
      return
    }

    setFieldErrors({})
    setBusy(true)
    try {
      await login({ email: validated.email, password: validated.password })
      navigate(postLoginPath, { replace: true })
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message)
      } else {
        setFormError('Unable to sign in. Please try again.')
      }
    } finally {
      setBusy(false)
    }
  }

  function onGoogle() {
    if (busy) return
    const androidNative = isNativeShell() && nativePlatform() === 'android'
    // OAuth next must remain a simple in-app path; push query destinations use native pending queue.
    const nextPath =
      postLoginPath.startsWith('/studio/fashionrise?') || postLoginPath.startsWith('/studio/runway?')
        ? '/studio/fashionrise'
        : postLoginPath.startsWith('/studio')
          ? postLoginPath.split('?')[0]
          : '/studio/home'
    const startUrl = getGoogleOAuthStartUrl(nextPath, {
      client: androidNative ? 'android' : 'web',
    })
    if (androidNative) {
      void openAndroidGoogleOAuth(startUrl)
      return
    }
    window.location.assign(startUrl)
  }

  return (
    <div className={styles.page}>
      <div className={styles.glow} aria-hidden />
      <div className={styles.card}>
        <div className={styles.brand}>
          <div className={styles.logoPlate}>
            <img
              src={UI_ASSETS.brand.login}
              alt="FashionRise"
              className={styles.logo}
              draggable={false}
            />
          </div>
        </div>

        <h2 className={styles.title}>Welcome back</h2>
        <p className={styles.subtitle}>Sign in to open Creator Studio.</p>

        {googleOAuthAvailable ? (
          <button
            type="button"
            className={styles.google}
            disabled={busy}
            onClick={onGoogle}
          >
            Continue with Google
          </button>
        ) : null}

        {googleOAuthAvailable ? (
          <p className={styles.orDivider} role="separator">
            or use email
          </p>
        ) : null}

        <form className={styles.form} onSubmit={onSubmit} noValidate>
          <label className={styles.field}>
            <span>Email</span>
            <input
              type="email"
              name="email"
              autoComplete="email"
              inputMode="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value)
                if (fieldErrors.email) setFieldErrors((prev) => ({ ...prev, email: undefined }))
              }}
              disabled={busy}
              aria-invalid={Boolean(fieldErrors.email)}
              aria-describedby={fieldErrors.email ? 'login-email-error' : undefined}
            />
            {fieldErrors.email ? (
              <span id="login-email-error" className={styles.fieldError} role="alert">
                {fieldErrors.email}
              </span>
            ) : null}
          </label>

          <label className={styles.field}>
            <span>Password</span>
            <div className={styles.passwordRow}>
              <input
                type={showPassword ? 'text' : 'password'}
                name="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value)
                  if (fieldErrors.password)
                    setFieldErrors((prev) => ({ ...prev, password: undefined }))
                }}
                disabled={busy}
                aria-invalid={Boolean(fieldErrors.password)}
                aria-describedby={fieldErrors.password ? 'login-password-error' : undefined}
              />
              <button
                type="button"
                className={styles.eye}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                onClick={() => setShowPassword((v) => !v)}
                disabled={busy}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            {fieldErrors.password ? (
              <span id="login-password-error" className={styles.fieldError} role="alert">
                {fieldErrors.password}
              </span>
            ) : null}
          </label>

          {passwordResetAvailable ? (
            <p className={styles.forgotRow}>
              <Link to="/forgot-password">Forgot password?</Link>
            </p>
          ) : null}

          {formError ? (
            <p className={styles.error} role="alert">
              {formError}
            </p>
          ) : null}

          <button type="submit" className={styles.submit} disabled={busy}>
            {busy ? 'Signing in…' : 'Enter Studio'}
          </button>
        </form>

        {showCreateAccount ? (
          <p className={styles.footerLinks}>
            Don&apos;t have an account? <Link to="/register">Create Account</Link>
          </p>
        ) : googleOAuthAvailable ? (
          <p className={styles.footerLinks}>
            No account yet? Continue with Google to create one automatically.
          </p>
        ) : null}
        <p className={styles.footerLinks}>
          <Link to="/privacy">Privacy Policy</Link>
        </p>
      </div>
    </div>
  )
}
