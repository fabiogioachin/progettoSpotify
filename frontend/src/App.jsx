import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import ErrorBoundary from './components/ErrorBoundary'
import AppLayout from './components/layout/AppLayout'
import LoadingSpinner from './components/ui/LoadingSpinner'

const LoginPage = lazy(() => import('./pages/LoginPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const PlaylistComparePage = lazy(() => import('./pages/PlaylistComparePage'))
const DiscoveryPage = lazy(() => import('./pages/DiscoveryPage'))
const TasteEvolutionPage = lazy(() => import('./pages/TasteEvolutionPage'))
const TemporalPage = lazy(() => import('./pages/TemporalPage'))
const ArtistNetworkPage = lazy(() => import('./pages/ArtistNetworkPage'))
const PlaylistAnalyticsPage = lazy(() => import('./pages/PlaylistAnalyticsPage'))
const WrappedPage = lazy(() => import('./pages/WrappedPage'))

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <LoadingSpinner fullScreen />
  if (!user) return <Navigate to="/" replace />
  return <AppLayout>{children}</AppLayout>
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
        <Route
          path="/evolution"
          element={
            <ProtectedRoute>
              <TasteEvolutionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/temporal"
          element={
            <ProtectedRoute>
              <TemporalPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/artists"
          element={
            <ProtectedRoute>
              <ArtistNetworkPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/playlist-analytics"
          element={
            <ProtectedRoute>
              <PlaylistAnalyticsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/wrapped"
          element={user ? <WrappedPage /> : <Navigate to="/" replace />}
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
