import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { UI_ASSETS } from '@/assets/uiAssets'
import { ApiError } from '@/services/api/client'
import { resetPassword } from '@/services/auth/authApi'
import { useAuth } from '@/services/auth/AuthProvider'
import styles from './RegisterPage.module.css'

function readTokenFromHash(): string {
  if (typeof window === 'undefined') return ''
  const raw = (window.location.hash || '').replace(/^#/, '')
  if (!raw) return ''
  const params = new URLSearchParams(raw)
  return (params.get('token') || '').trim()
}

function clearHashFromHistory(): void {
  if (typeof window === 'undefined') return
  const { pathname, search } = window.location
  window.history.replaceState(null, '', `${pathname}${search}`)
}

function hasQueryToken(): boolean {
  if (typeof window === 'undefined') return false
  return Boolean(new URLSearchParams(window.location.search).get('token'))
}

/**
 * Password reset handoff. Opening the link never redeems the token — only an
 * explicit Save password POST does. A valid hash token always shows this form,
 * even if another FashionRise session is already signed in.
 */
export function ResetPasswordPage() {
  const { user, isAuthenticated, bootstrapping, refreshUser, passwordResetAvailable } = useAuth()
  const navigate = useNavigate()
  // Capture token on first paint so an existing session cannot Navigate away first.
  const [token, setToken] = useState<string | null>(() => {
    if (hasQueryToken()) return null
    const fromHash = readTokenFromHash()
    return fromHash || null
  })
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [queryTokenRejected, setQueryTokenRejected] = useState(() => hasQueryToken())
  const [hashScrubbed, setHashScrubbed] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const search = new URLSearchParams(window.location.search)
    if (search.get('token')) {
      setQueryTokenRejected(true)
      setToken(null)
      const url = new URL(window.location.href)
      url.searchParams.delete('token')
      window.history.replaceState(null, '', `${url.pathname}${url.search}`)
      return
    }
    const fromHash = readTokenFromHash()
    if (fromHash) {
      setToken(fromHash)
      clearHashFromHistory()
      setHashScrubbed(true)
      return
    }
    if (token && !hashScrubbed) {
      // Token already captured via useState initializer — scrub hash if still present.
      clearHashFromHistory()
      setHashScrubbed(true)
    }
  }, [token, hashScrubbed])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!token || busy) return
    setError(null)
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    if (!passwordResetAvailable) {
      setError('Password reset is not available right now.')
      return
    }
    setBusy(true)
    try {
      await resetPassword(token, password)
      await refreshUser().catch(() => undefined)
      navigate('/studio/home', { replace: true })
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message || 'Unable to reset password.')
      } else {
        setError('Unable to reset password. Request a new link from the sign-in page.')
      }
      setBusy(false)
    }
  }

  if (bootstrapping) return null

  // Never bounce a valid reset intent into Studio — form stays compact / mobile-safe.
  const hasResetIntent = Boolean(token) || queryTokenRejected
  if (isAuthenticated && !busy && !error && !hasResetIntent) {
    return <Navigate to="/studio/home" replace />
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
        <h1 className={styles.title}>Choose a new password</h1>
        {queryTokenRejected ? (
          <p className={styles.subtitle}>
            This reset link used an unsafe format. Open the latest email link (it should not put
            the token in the page address before the #), or{' '}
            <Link to="/forgot-password">request a new reset email</Link>.
          </p>
        ) : !token ? (
          <p className={styles.subtitle}>
            Open the reset link from your email to continue, or{' '}
            <Link to="/forgot-password">request a new link</Link>.
          </p>
        ) : (
          <>
            <p className={styles.subtitle}>
              Enter a new password for your FashionRise account. Opening this page alone does not
              change your password.
            </p>
            {isAuthenticated && user?.username ? (
              <p className={styles.subtitle} role="status">
                You are signed in as <strong>{user.username}</strong>. Saving a new password signs
                you into the account for this reset link (and ends the current session).
              </p>
            ) : null}
            <form className={styles.form} onSubmit={(e) => void onSubmit(e)} noValidate>
              <label className={styles.field}>
                <span>New password</span>
                <input
                  type="password"
                  name="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={busy}
                />
              </label>
              <label className={styles.field}>
                <span>Confirm password</span>
                <input
                  type="password"
                  name="confirm"
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  disabled={busy}
                />
              </label>
              {error ? (
                <p className={styles.error} role="alert">
                  {error}
                </p>
              ) : null}
              <button type="submit" className={styles.submit} disabled={busy}>
                {busy ? 'Saving…' : 'Save password'}
              </button>
            </form>
            <p className={styles.footerLinks}>
              <Link to="/login">Sign in</Link>
              {' · '}
              <Link to="/forgot-password">Request a new link</Link>
            </p>
          </>
        )}
      </div>
    </div>
  )
}
