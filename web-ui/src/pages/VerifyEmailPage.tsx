import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { UI_ASSETS } from '@/assets/uiAssets'
import { ApiError } from '@/services/api/client'
import { verifyEmail } from '@/services/auth/authApi'
import { useAuth } from '@/services/auth/AuthProvider'
import styles from './RegisterPage.module.css'

export function VerifyEmailPage() {
  const { isAuthenticated, bootstrapping, refreshUser } = useAuth()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = (searchParams.get('token') || '').trim()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(Boolean(token))

  useEffect(() => {
    if (!token || bootstrapping) return
    let cancelled = false
    ;(async () => {
      setBusy(true)
      setError(null)
      try {
        await verifyEmail(token)
        if (!cancelled) {
          await refreshUser().catch(() => undefined)
          navigate('/studio/home', { replace: true })
        }
      } catch (err) {
        if (cancelled) return
        if (err instanceof ApiError) {
          setError(err.message || 'Verification failed.')
        } else {
          setError('Verification failed. Request a new link from the registration page.')
        }
        setBusy(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token, bootstrapping, navigate, refreshUser])

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
        {!token ? (
          <p className={styles.subtitle}>
            This verification link is missing a token. Open the link from your email, or{' '}
            <Link to="/register">create an account</Link>.
          </p>
        ) : busy ? (
          <p className={styles.subtitle}>Confirming your email…</p>
        ) : (
          <>
            <p className={styles.error} role="alert">
              {error}
            </p>
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
