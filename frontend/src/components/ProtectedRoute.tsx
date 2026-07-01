import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute() {
  const { user, loading } = useAuth()

  if (loading) return <div className="spinner-wrap"><div className="spinner" /></div>
  if (!user) return <Navigate to="/login" replace />
  if (user.must_change_password) return <Navigate to="/change-password" replace />
  return <Outlet />
}
