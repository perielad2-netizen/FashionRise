import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { UI_ASSETS } from '@/assets/uiAssets'
import { mapRegisterError } from '@/lib/mapRegisterError'
import { validateRegister, type RegisterFieldErrors } from '@/lib/validateRegister'
import { ApiError } from '@/services/api/client'
import { useAuth } from '@/services/auth/AuthProvider'
import styles from './RegisterPage.module.css'

function initialFromQuery(params: URLSearchParams, key: string): string {
  return (params.get(key) || '').trim()
}

export function RegisterPage() {
  const { register, isAuthenticated, bootstrapping } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  // Email-only query prefill is safe. Never put invitation tokens in URL query params
  // (logs, history, Referer). Invitees paste the out-of-band code into the form.
  const [email, setEmail] = useState(() => initialFromQuery(searchParams, 'email'))
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [invitationCode, setInvitationCode] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<RegisterFieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [uncertain, setUncertain] = useState(false)
  const [busy, setBusy] = useState(false)

  if (bootstrapping) return null
  if (isAuthenticated) return <Navigate to="/studio" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (busy) return

    // After an uncertain outcome, do not POST /register again — recover via sign-in.
    if (uncertain) {
      navigate('/login')
      return
    }

    setFormError(null)
    setUncertain(false)
    const validated = validateRegister({
      email,
      username,
      displayName,
      password,
      confirmPassword,
      invitationCode,
    })
    if (!validated.ok) {
      setFieldErrors(validated.errors)
      return
    }

    setFieldErrors({})
    setBusy(true)
    try {
      await register({
        email: validated.email,
        username: validated.username,
        password: validated.password,
        displayName: validated.displayName,
        invitationCode: validated.invitationCode,
      })
      navigate('/studio', { replace: true })
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 0 || err.status >= 500) {
          setUncertain(true)
        }
        setFormError(mapRegisterError(err))
      } else {
        setUncertain(true)
        setFormError('Unable to create your account. Please try again or sign in.')
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

        <h1 className={styles.title}>Create account</h1>
        <p className={styles.subtitle}>
          Enter your invitation details to join FashionRise and open Creator Studio.
        </p>

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
              aria-describedby={fieldErrors.email ? 'register-email-error' : undefined}
            />
            {fieldErrors.email ? (
              <span id="register-email-error" className={styles.fieldError} role="alert">
                {fieldErrors.email}
              </span>
            ) : null}
          </label>

          <label className={styles.field}>
            <span>Username</span>
            <input
              type="text"
              name="username"
              autoComplete="username"
              value={username}
              onChange={(e) => {
                setUsername(e.target.value)
                if (fieldErrors.username)
                  setFieldErrors((prev) => ({ ...prev, username: undefined }))
              }}
              disabled={busy}
              aria-invalid={Boolean(fieldErrors.username)}
              aria-describedby={fieldErrors.username ? 'register-username-error' : undefined}
            />
            {fieldErrors.username ? (
              <span id="register-username-error" className={styles.fieldError} role="alert">
                {fieldErrors.username}
              </span>
            ) : null}
          </label>

          <label className={styles.field}>
            <span>Display name (optional)</span>
            <input
              type="text"
              name="displayName"
              autoComplete="nickname"
              value={displayName}
              onChange={(e) => {
                setDisplayName(e.target.value)
                if (fieldErrors.displayName)
                  setFieldErrors((prev) => ({ ...prev, displayName: undefined }))
              }}
              disabled={busy}
              aria-invalid={Boolean(fieldErrors.displayName)}
              aria-describedby={fieldErrors.displayName ? 'register-display-error' : undefined}
            />
            {fieldErrors.displayName ? (
              <span id="register-display-error" className={styles.fieldError} role="alert">
                {fieldErrors.displayName}
              </span>
            ) : null}
          </label>

          <label className={styles.field}>
            <span>Password</span>
            <div className={styles.passwordRow}>
              <input
                type={showPassword ? 'text' : 'password'}
                name="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value)
                  if (fieldErrors.password)
                    setFieldErrors((prev) => ({ ...prev, password: undefined }))
                }}
                disabled={busy}
                aria-invalid={Boolean(fieldErrors.password)}
                aria-describedby={fieldErrors.password ? 'register-password-error' : undefined}
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
              <span id="register-password-error" className={styles.fieldError} role="alert">
                {fieldErrors.password}
              </span>
            ) : null}
          </label>

          <label className={styles.field}>
            <span>Confirm password</span>
            <div className={styles.passwordRow}>
              <input
                type={showConfirm ? 'text' : 'password'}
                name="confirmPassword"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value)
                  if (fieldErrors.confirmPassword)
                    setFieldErrors((prev) => ({ ...prev, confirmPassword: undefined }))
                }}
                disabled={busy}
                aria-invalid={Boolean(fieldErrors.confirmPassword)}
                aria-describedby={
                  fieldErrors.confirmPassword ? 'register-confirm-error' : undefined
                }
              />
              <button
                type="button"
                className={styles.eye}
                aria-label={showConfirm ? 'Hide confirm password' : 'Show confirm password'}
                onClick={() => setShowConfirm((v) => !v)}
                disabled={busy}
              >
                {showConfirm ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            {fieldErrors.confirmPassword ? (
              <span id="register-confirm-error" className={styles.fieldError} role="alert">
                {fieldErrors.confirmPassword}
              </span>
            ) : null}
          </label>

          <label className={styles.field}>
            <span>Invitation code</span>
            <input
              type="text"
              name="invitationCode"
              autoComplete="one-time-code"
              spellCheck={false}
              value={invitationCode}
              onChange={(e) => {
                setInvitationCode(e.target.value)
                if (fieldErrors.invitationCode)
                  setFieldErrors((prev) => ({ ...prev, invitationCode: undefined }))
              }}
              disabled={busy}
              aria-invalid={Boolean(fieldErrors.invitationCode)}
              aria-describedby={
                fieldErrors.invitationCode
                  ? 'register-invite-error'
                  : 'register-invite-hint'
              }
            />
            {fieldErrors.invitationCode ? (
              <span id="register-invite-error" className={styles.fieldError} role="alert">
                {fieldErrors.invitationCode}
              </span>
            ) : (
              <span id="register-invite-hint" className={styles.hintInline}>
                Paste the one-time code from your operator. Email must match the invite.
              </span>
            )}
          </label>

          {formError ? (
            <p className={styles.error} role="alert">
              {formError}
            </p>
          ) : null}

          {uncertain ? (
            <p className={styles.hint} role="status">
              If the network dropped after you submitted, do not keep creating accounts. Try{' '}
              <Link to="/login">signing in</Link> with this email and password.
            </p>
          ) : null}

          <button type="submit" className={styles.submit} disabled={busy}>
            {busy ? 'Creating account…' : uncertain ? 'Sign in instead' : 'Create account'}
          </button>
        </form>

        <p className={styles.footerLinks}>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
