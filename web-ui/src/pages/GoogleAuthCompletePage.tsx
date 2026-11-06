import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { completeGoogleOAuthSession } from '@/services/auth/authApi'
import styles from './LoginPage.module.css'

function parseHashTokens(hash: string): {
  access_token: string
  refresh_token: string
  next: string
} | null {
  const raw = hash.startsWith('#') ? hash.slice(1) : hash
  if (!raw) return null
  const params = new URLSearchParams(raw)
  const access = params.get('access_token') || ''
  const refresh = params.get('refresh_token') || ''
  const nextRaw = params.get('next') || '/studio'
  const next = nextRaw.startsWith('/') && !nextRaw.startsWith('//') ? nextRaw : '/studio'
  if (!access || !refresh) return null
  return { access_token: access, refresh_token: refresh, next }
}

/**
 * Landing page after Google OAuth callback. Reads tokens from the URL hash,
 * stores the session, clears the hash, then hard-navigates into Studio so
 * AuthProvider restores from tokenStore.
 */
export function GoogleAuthCompletePage() {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const parsed = parseHashTokens(window.location.hash)
      if (window.location.hash) {
        window.history.replaceState(null, '', window.location.pathname + window.location.search)
      }
      if (!parsed) {
        if (!cancelled) setError('Google sign-in did not return a session. Try again.')
        return
      }
      try {
        await completeGoogleOAuthSession(parsed)
        if (cancelled) return
        window.location.replace(parsed.next)
      } catch {
        if (!cancelled) setError('Could not finish Google sign-in. Please try again.')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className={styles.page}>
      <div className={styles.glow} aria-hidden />
      <div className={styles.card}>
        <h2 className={styles.title}>{error ? 'Sign-in failed' : 'Signing you in…'}</h2>
        <p className={styles.subtitle}>
          {error ?? 'Finishing Google sign-in for FashionRise.'}
        </p>
        {error ? (
          <button
            type="button"
            className={styles.submit}
            onClick={() => navigate('/login', { replace: true })}
          >
            Back to sign in
          </button>
        ) : null}
      </div>
    </div>
  )
}
