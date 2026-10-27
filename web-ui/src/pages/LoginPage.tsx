import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { UI_ASSETS } from '@/assets/uiAssets'
import { isRegistrationUiEnabled } from '@/config/registrationUi'
import { validateLogin, type LoginFieldErrors } from '@/lib/validateLogin'
import { ApiError } from '@/services/api/client'
import { useAuth } from '@/services/auth/AuthProvider'
import styles from './LoginPage.module.css'

export function LoginPage() {
  const { login, loginWithAccess, isAuthenticated, bootstrapping, accessSsoAvailable } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<LoginFieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [accessHint, setAccessHint] = useState<string | null>(null)

  useEffect(() => {
    if (!accessSsoAvailable) {
      setAccessHint(null)
      return
    }
    setAccessHint(
      'Cloudflare Access verified — continue with FashionRise credentials if automatic sign-in did not complete.',
    )
  }, [accessSsoAvailable])

  if (bootstrapping) return null
  if (isAuthenticated) return <Navigate to="/studio" replace />

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
      navigate('/studio', { replace: true })
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
        {accessHint ? <p className={styles.subtitle}>{accessHint}</p> : null}
        {accessSsoAvailable && loginWithAccess ? (
          <button
            type="button"
            className={styles.submit}
            style={{ marginBottom: 12 }}
            disabled={busy}
            onClick={() => {
              void (async () => {
                setBusy(true)
                setFormError(null)
                const ok = await loginWithAccess()
                setBusy(false)
                if (ok) navigate('/studio', { replace: true })
                else
                  setFormError(
                    'Could not link Cloudflare Access to a FashionRise account. Sign in with email below once.',
                  )
              })()
            }}
          >
            Continue with Cloudflare Access
          </button>
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

          {formError ? (
            <p className={styles.error} role="alert">
              {formError}
            </p>
          ) : null}

          <button type="submit" className={styles.submit} disabled={busy}>
            {busy ? 'Signing in…' : 'Enter Studio'}
          </button>
        </form>

        {isRegistrationUiEnabled() ? (
          <p className={styles.footerLinks}>
            Invited to the beta? <Link to="/register">Create account</Link>
          </p>
        ) : null}
      </div>
    </div>
  )
}
