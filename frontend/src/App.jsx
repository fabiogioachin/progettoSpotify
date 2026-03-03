import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import ErrorBoundary from './components/ErrorBoundary'
import LoadingSpinner from './components/ui/LoadingSpinner'

const LoginPage = lazy(() => import('./pages/LoginPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const PlaylistComparePage = lazy(() => import('./pages/PlaylistComparePage'))
const DiscoveryPage = lazy(() => import('./pages/DiscoveryPage'))

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <LoadingSpinner fullScreen />
  if (!user) return <Navigate to="/" replace />
  return children
}

function AppRoutes() {
  const { user, loading } = useAuth()

  if (loading) return <LoadingSpinner fullScreen />

  return (
    <Suspense fallback={<LoadingSpinner fullScreen />}>
      <Routes>
        <Route
          path="/"
          element={user ? <Navigate to="/dashboard" replace /> : <LoginPage />}
        />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/playlists"
          element={
            <ProtectedRoute>
              <PlaylistComparePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/discovery"
          element={
            <ProtectedRoute>
              <DiscoveryPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ErrorBoundary>
          <AppRoutes />
        </ErrorBoundary>
      </AuthProvider>
    </BrowserRouter>
  )
}
