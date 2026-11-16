import { createContext, useContext, useState, type ReactNode } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import type { Assignment, Role } from '../api/types'
import { useAuth } from './AuthProvider'
import { Notice } from '../components/ui'

export const roleLabels: Record<Role, string> = { PRODUCCION: 'Producción', TRANSPORTE: 'Transporte', RECEPCION: 'Recepción', ADMIN: 'Administración', GALPONERO: 'Cuyes · Galponero' }
export type NavIconName = 'home' | 'production' | 'cows' | 'history' | 'transport' | 'pending' | 'reception' | 'admin' | 'trace' | 'users' | 'catalog' | 'help'
export const navigation: Record<Role, { to: string; label: string; icon: NavIconName }[]> = {
  GALPONERO: [{ to: '/cuyes', label: 'Cuyes', icon: 'home' }, { to: '/sincronizacion', label: 'Sincronización', icon: 'pending' }, { to: '/ayuda', label: 'Ayuda', icon: 'help' }],
  PRODUCCION: [{ to: '/hoy', label: 'Hoy', icon: 'home' }, { to: '/produccion', label: 'Producción', icon: 'production' }, { to: '/vacas', label: 'Vacas', icon: 'cows' }, { to: '/historial', label: 'Historial', icon: 'history' }, { to: '/ayuda', label: 'Ayuda', icon: 'help' }],
  TRANSPORTE: [{ to: '/hoy', label: 'Hoy', icon: 'home' }, { to: '/diario', label: 'Diario', icon: 'transport' }, { to: '/pendientes', label: 'Pendientes', icon: 'pending' }, { to: '/ayuda', label: 'Ayuda', icon: 'help' }],
  RECEPCION: [{ to: '/hoy', label: 'Hoy', icon: 'home' }, { to: '/recepciones', label: 'Recepciones', icon: 'reception' }, { to: '/pendientes', label: 'Pendientes', icon: 'pending' }, { to: '/ayuda', label: 'Ayuda', icon: 'help' }],
  ADMIN: [{ to: '/hoy', label: 'Resumen', icon: 'home' }, { to: '/administracion', label: 'Administrar', icon: 'admin' }, { to: '/administracion/lotes', label: 'Trazabilidad', icon: 'trace' }, { to: '/administracion/usuarios', label: 'Cuentas', icon: 'users' }, { to: '/administracion/catalogos', label: 'Catálogos', icon: 'catalog' }, { to: '/cuyes', label: 'Cuyes', icon: 'home' }, { to: '/ayuda', label: 'Ayuda', icon: 'help' }],
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
