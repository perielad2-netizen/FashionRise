import { Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import { LoginPage } from '@/pages/LoginPage'
import { StudioPage } from '@/pages/StudioPage'
import { AuthProvider, useAuth } from '@/services/auth/AuthProvider'

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
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </AuthProvider>
  )
}
