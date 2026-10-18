import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/services/auth/AuthProvider'
import styles from './ProtectedRoute.module.css'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, bootstrapping } = useAuth()
  const location = useLocation()

  if (bootstrapping) {
    return (
      <div className={styles.boot} role="status" aria-live="polite">
        <div className={styles.mark}>FR</div>
        <p>Opening FashionRise…</p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}
