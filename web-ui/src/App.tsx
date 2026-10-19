import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { LoginPage } from '@/pages/LoginPage'
import { StudioPage } from '@/pages/StudioPage'
import { AuthProvider, useAuth } from '@/services/auth/AuthProvider'

const DesignStudioLabPage = import.meta.env.DEV
  ? lazy(() =>
      import('@/design-lab/DesignStudioLabPage').then((m) => ({
        default: m.DesignStudioLabPage,
      })),
    )
  : null

function RootRedirect() {
  const { isAuthenticated, bootstrapping } = useAuth()
  if (bootstrapping) return null
  return <Navigate to={isAuthenticated ? '/studio' : '/login'} replace />
}

export default function App() {
  return (
    <AuthProvider>
      <div className="app-root">
        <Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/studio"
            element={
              <ProtectedRoute>
                <StudioPage />
              </ProtectedRoute>
            }
          />
          {import.meta.env.DEV && DesignStudioLabPage ? (
            <Route
              path="/_design/studio"
              element={
                <Suspense
                  fallback={
                    <div style={{ padding: 24, color: '#f8f4f0' }}>Loading design lab…</div>
                  }
                >
                  <DesignStudioLabPage />
                </Suspense>
              }
            />
          ) : null}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </AuthProvider>
  )
}
