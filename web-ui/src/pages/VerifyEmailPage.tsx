import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { UI_ASSETS } from '@/assets/uiAssets'
import { ApiError } from '@/services/api/client'
import { verifyEmail } from '@/services/auth/authApi'
import { useAuth } from '@/services/auth/AuthProvider'
import styles from './RegisterPage.module.css'

function readTokenFromHash(): string {
  if (typeof window === 'undefined') return ''
  const raw = (window.location.hash || '').replace(/^#/, '')
  if (!raw) return ''
  const params = new URLSearchParams(raw)
  return (params.get('token') || '').trim()
}

/**
 * Clear the fragment from the address bar / history without a navigation.
 * Prevents the raw token from lingering in history or being re-shared.
 */
function clearHashFromHistory(): void {
  if (typeof window === 'undefined') return
  const { pathname, search } = window.location
  window.history.replaceState(null, '', `${pathname}${search}`)
}

export function VerifyEmailPage() {
  const { isAuthenticated, bootstrapping, refreshUser } = useAuth()
  const navigate = useNavigate()
  const [token, setToken] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [queryTokenRejected, setQueryTokenRejected] = useState(false)

  // Read fragment once on mount. Never auto-consume — scanners that only GET
  // the HTML cannot verify. Explicit user confirmation required.
  useEffect(() => {
    if (typeof window === 'undefined') return
    const search = new URLSearchParams(window.location.search)
    if (search.get('token')) {
      // Query-string tokens would hit access logs — refuse and scrub the URL.
      setQueryTokenRejected(true)
      clearHashFromHistory()
      const url = new URL(window.location.href)
      url.searchParams.delete('token')
      window.history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`)
      return
    }
    const fromHash = readTokenFromHash()
    if (fromHash) {
      setToken(fromHash)
      clearHashFromHistory()
    }
  }, [])

  async function onConfirm() {
    if (!token || busy) return
    setBusy(true)
    setError(null)
    try {
      await verifyEmail(token)
      await refreshUser().catch(() => undefined)
      navigate('/studio/home', { replace: true })
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message || 'Verification failed.')
      } else {
        setError('Verification failed. Request a new link from the registration page.')
      }
      setBusy(false)
    }
  }

  if (bootstrapping) return null
  if (isAuthenticated && !busy && !error) return <Navigate to="/studio/home" replace />

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
        <h1 className={styles.title}>Verify email</h1>
        {queryTokenRejected ? (
          <p className={styles.subtitle}>
            This verification link used an unsafe format. Open the latest email link (it should
            not put the token in the page address before the #), or{' '}
            <Link to="/register">request a new verification email</Link>.
          </p>
        ) : !token ? (
          <p className={styles.subtitle}>
            Open the verification link from your email to continue, or{' '}
            <Link to="/register">create an account</Link>.
          </p>
        ) : (
          <>
            <p className={styles.subtitle}>
              Confirm your email address to finish creating your FashionRise account. Opening
              this page alone does not verify you.
            </p>
            {error ? (
              <p className={styles.error} role="alert">
                {error}
              </p>
            ) : null}
            <button
              type="button"
              className={styles.submit}
              disabled={busy}
              onClick={() => void onConfirm()}
            >
              {busy ? 'Verifying…' : 'Confirm email'}
            </button>
            <p className={styles.footerLinks}>
              <Link to="/login">Sign in</Link>
              {' · '}
              <Link to="/register">Create Account</Link>
            </p>
          </>
        )}
      </div>
    </div>
  )
}
