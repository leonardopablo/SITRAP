import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './AuthProvider'
import { Notice } from '../components/ui'

export function RequireAuth() {
  const { account, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Notice>Comprobando sesión…</Notice>
  if (!account) return <Navigate to="/acceso" state={{ from: location.pathname + location.search }} replace />
  if (account.change_password_required && location.pathname !== '/cuenta/clave') return <Navigate to="/cuenta/clave" replace />
  return <Outlet />
}
