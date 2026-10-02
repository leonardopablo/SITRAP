import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { navigation, roleLabels, useWorkspace } from '../auth/workspace'
import { Button, Dialog, Notice } from './ui'
import { SyncStatus } from '../offline/SyncPanel'
import { useConnection } from '../offline/SyncPanel'
import { pendingCount } from '../offline/db'
import { applyChanges } from '../offline/prepare'
import { syncAccount } from '../offline/sync'
import { apiMode } from '../api/client'
import { InboxBell } from '../notifications/Inbox'

export function Shell() {
  const { account, logout, lock } = useAuth()
  const online = useConnection()
  const { assignment, select } = useWorkspace()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState(false)
  useEffect(() => {
    if (!account || apiMode !== 'http') return
    let working = false
    const update = async () => {
      if (working || !navigator.onLine || document.hidden) return
      working = true
      try { await applyChanges(account.id); await syncAccount(account.id) } catch { /* panel exposes recoverable details; do not claim success */ }
      finally { working = false }
    }
    void update()
    const focus = () => void update()
    window.addEventListener('focus', focus); window.addEventListener('online', focus)
    return () => { window.removeEventListener('focus', focus); window.removeEventListener('online', focus) }
  }, [account?.id])
  async function closeSession() {
    setBusy(true); setError('')
    try {
      if (online) await logout()
      else { await lock(); setError('') }
      navigate('/acceso')
    } catch { setError('No se pudo cerrar la sesión central. Reintenta con conexión.') }
    finally { setBusy(false); setConfirm(false) }
  }
  return <div className="workspace">
    <aside className="workspace-sidebar">
      <section className="card stack" aria-label="Cuenta y ámbito activos">
        <strong>{account?.name}</strong><span>@{account?.username}</span>
        {assignment && <><span className="badge">{roleLabels[assignment.role]}</span><span>{assignment.location_name}</span></>}
        {(account?.assignments.length ?? 0) > 1 && <div className="field"><label htmlFor="workspace">Espacio de trabajo</label><select id="workspace" value={assignment?.id} onChange={event => { select(event.target.value); navigate('/hoy') }}>
          {account?.assignments.map(item => <option key={item.id} value={item.id}>{roleLabels[item.role]} · {item.location_name}</option>)}
        </select></div>}
        <Link to="/cuenta/clave">Cambiar contraseña</Link>
        <SyncStatus />
        <InboxBell />
        <Button variant="secondary" busy={busy} onClick={async () => { if (account && await pendingCount(account.id)) setConfirm(true); else await closeSession() }}>Cerrar sesión</Button>
        {!online && <Notice tone="warning">Sin conexión: al cerrar solo se bloquea este teléfono. La sesión central seguirá activa hasta recuperar conexión y revocarla.</Notice>}
        <Dialog open={confirm} title="Operaciones pendientes" onClose={() => setConfirm(false)}><p>Hay registros guardados solo en este teléfono. Puedes sincronizarlos primero o cerrar conservándolos bloqueados para esta misma cuenta.</p><div className="row"><Button variant="secondary" onClick={() => { setConfirm(false); navigate('/sincronizacion') }}>Sincronizar primero</Button><Button onClick={() => void closeSession()}>Cerrar y conservar</Button></div></Dialog>
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
