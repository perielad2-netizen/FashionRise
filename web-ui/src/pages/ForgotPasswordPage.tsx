import { useState, type FormEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { UI_ASSETS } from '@/assets/uiAssets'
import { ApiError } from '@/services/api/client'
import { requestPasswordReset } from '@/services/auth/authApi'
import { useAuth } from '@/services/auth/AuthProvider'
import styles from './RegisterPage.module.css'

function looksLikeEmail(value: string): boolean {
  const v = value.trim()
  return v.includes('@') && v.includes('.') && v.length >= 5
}

export function ForgotPasswordPage() {
  const { isAuthenticated, bootstrapping, passwordResetAvailable } = useAuth()
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)

  if (bootstrapping) return null
  if (isAuthenticated) return <Navigate to="/studio/home" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (busy) return
    setError(null)
    if (!looksLikeEmail(email)) {
      setError('Enter a valid email address.')
      return
    }
    if (!passwordResetAvailable) {
      setError('Password reset is not available right now. Try again later or contact support.')
      return
    }
    setBusy(true)
    try {
      await requestPasswordReset(email)
      setSent(true)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message || 'Unable to send reset email.')
      } else {
        setError('Unable to send reset email. Please try again.')
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
        <h1 className={styles.title}>Forgot password</h1>
        {!passwordResetAvailable && !sent ? (
          <>
            <p className={styles.subtitle}>
              Password reset is not available on this environment yet. You can still sign in with
              your current password or Google.
            </p>
            <p className={styles.footerLinks}>
              <Link to="/login">Back to sign in</Link>
            </p>
          </>
        ) : sent ? (
          <>
            <p className={styles.subtitle}>
              If an account exists for that email, we sent a reset link. Check your inbox and spam
              folder. The link expires soon and can be used only once.
            </p>
            <p className={styles.footerLinks}>
              <Link to="/login">Back to sign in</Link>
            </p>
          </>
        ) : (
          <>
            <p className={styles.subtitle}>
              Enter your account email and we will send a one-time link to choose a new password.
            </p>
            <form className={styles.form} onSubmit={(e) => void onSubmit(e)} noValidate>
              <label className={styles.field}>
                <span>Email</span>
                <input
                  type="email"
                  name="email"
                  autoComplete="email"
                  inputMode="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={busy}
                />
              </label>
              {error ? (
                <p className={styles.error} role="alert">
                  {error}
                </p>
              ) : null}
              <button type="submit" className={styles.submit} disabled={busy}>
                {busy ? 'Sending…' : 'Send reset link'}
              </button>
            </form>
            <p className={styles.footerLinks}>
              <Link to="/login">Back to sign in</Link>
            </p>
          </>
        )}
      </div>
    </div>
  )
}
