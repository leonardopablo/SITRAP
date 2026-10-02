import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { navigation, roleLabels, useWorkspace } from '../auth/workspace'
import { Button, Notice } from './ui'

export function Shell() {
  const { account, logout } = useAuth()
  const { assignment, select } = useWorkspace()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  return <div className="workspace">
    <aside className="workspace-sidebar">
      <section className="card stack" aria-label="Cuenta y ámbito activos">
        <strong>{account?.name}</strong><span>@{account?.username}</span>
        {assignment && <><span className="badge">{roleLabels[assignment.role]}</span><span>{assignment.location_name}</span></>}
        {(account?.assignments.length ?? 0) > 1 && <div className="field"><label htmlFor="workspace">Espacio de trabajo</label><select id="workspace" value={assignment?.id} onChange={event => { select(event.target.value); navigate('/hoy') }}>
          {account?.assignments.map(item => <option key={item.id} value={item.id}>{roleLabels[item.role]} · {item.location_name}</option>)}
        </select></div>}
        <Link to="/cuenta/clave">Cambiar contraseña</Link>
        <Button variant="secondary" busy={busy} onClick={async () => { setBusy(true); setError(''); try { await logout(); navigate('/acceso') } catch { setError('No se pudo cerrar la sesión central. Reintenta con conexión.') } finally { setBusy(false) } }}>Cerrar sesión</Button>
        {error && <Notice tone="error">{error}</Notice>}
      </section>
      {assignment && <nav className="workspace-nav" aria-label="Navegación principal">{navigation[assignment.role].map(item => <NavLink key={item.to} to={item.to}>{item.label}</NavLink>)}</nav>}
    </aside>
    <div className="workspace-content" key={`${account?.id}:${assignment?.id}`}><Outlet /></div>
  </div>
}

export function TodayPage() {
  const { assignment } = useWorkspace()
  return <section className="card"><h1>{assignment?.role === 'ADMIN' ? 'Resumen administrativo' : 'Hoy'}</h1>
    <p>{new Intl.DateTimeFormat('es-PE', { dateStyle: 'full', timeZone: 'America/Lima' }).format(new Date())}</p>
    <Notice>{assignment ? `Espacio de ${roleLabels[assignment.role].toLowerCase()} preparado. Las tareas operativas se incorporarán en los siguientes incrementos.` : 'No tienes asignaciones activas. Contacta al administrador.'}</Notice>
  </section>
}
export function PendingFeature({ title }: { title: string }) {
  return <section className="card"><h1>{title}</h1><Notice>Funcionalidad pendiente de implementación. Esta pantalla solo permite verificar la navegación.</Notice></section>
}
