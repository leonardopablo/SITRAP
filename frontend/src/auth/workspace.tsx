import { createContext, useContext, useState, type ReactNode } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import type { Assignment, Role } from '../api/types'
import { useAuth } from './AuthProvider'
import { Notice } from '../components/ui'

export const roleLabels: Record<Role, string> = { PRODUCCION: 'Producción', TRANSPORTE: 'Transporte', RECEPCION: 'Recepción', ADMIN: 'Administración' }
export const navigation: Record<Role, { to: string; label: string }[]> = {
  PRODUCCION: [{ to: '/hoy', label: 'Hoy' }, { to: '/produccion', label: 'Producción' }, { to: '/vacas', label: 'Vacas' }, { to: '/historial', label: 'Historial' }],
  TRANSPORTE: [{ to: '/hoy', label: 'Hoy' }, { to: '/diario', label: 'Diario' }, { to: '/pendientes', label: 'Pendientes' }],
  RECEPCION: [{ to: '/hoy', label: 'Hoy' }, { to: '/recepciones', label: 'Recepciones' }, { to: '/pendientes', label: 'Pendientes' }],
  ADMIN: [{ to: '/hoy', label: 'Resumen' }, { to: '/administracion', label: 'Administrar' }, { to: '/reportes', label: 'Reportes' }],
}
const Context = createContext<{ assignment: Assignment | null; select: (id: string) => void }>({ assignment: null, select: () => {} })
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { account } = useAuth()
  const cache = useQueryClient()
  const [selected, setSelected] = useState<{ account: string; assignment: string } | null>(null)
  const assignment = (selected?.account === account?.id ? account?.assignments.find(item => item.id === selected?.assignment) : undefined) ?? account?.assignments[0] ?? null
  function select(id: string) {
    if (!account?.assignments.some(item => item.id === id)) return
    cache.clear()
    setSelected({ account: account.id, assignment: id })
  }
  return <Context.Provider value={{ assignment, select }}>{children}</Context.Provider>
}
export const useWorkspace = () => useContext(Context)
export function RequireRole({ roles }: { roles: Role[] }) {
  const { assignment } = useWorkspace()
  if (!assignment) return <Notice tone="warning">No tienes asignaciones activas. Contacta al administrador.</Notice>
  if (!roles.includes(assignment.role)) return <Navigate to="/hoy" replace />
  return <Outlet />
}
