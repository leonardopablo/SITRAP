import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiMode } from '../api/client'
import type { Page, Role } from '../api/types'
import { useAuth } from '../auth/AuthProvider'
import { useConnection } from '../offline/SyncPanel'
import { Button, Notice } from '../components/ui'

interface User { id: string; username: string; name: string; active: boolean; change_password_required: boolean }
interface Assignment { id: string; user_id: string; role: Role; scope: string; location_id: string | null; active: boolean }
export function UsersPage() {
  const { account } = useAuth()
  const online = useConnection()
  const cache = useQueryClient()
  const [username, setUsername] = useState('')
  const [name, setName] = useState('')
  const [userId, setUserId] = useState('')
  const [role, setRole] = useState<Role>('PRODUCCION')
  const [location, setLocation] = useState('')
  const [message, setMessage] = useState('')
  const [temporary, setTemporary] = useState('')
  const [busy, setBusy] = useState(false)
  const users = useQuery({ queryKey: ['users', account?.id], queryFn: () => api.request<Page<User>>('/users'), enabled: !!account && online })
  const assignments = useQuery({ queryKey: ['role-assignments', account?.id], queryFn: () => api.request<Page<Assignment>>('/role-assignments'), enabled: !!account && online })
  const locations = useQuery({ queryKey: ['admin-locations', account?.id], queryFn: () => api.request<Page<{ id: string; name: string; type: string }>>('/locations'), enabled: !!account && online })
  async function run(action: () => Promise<unknown>, success: string) { setBusy(true); setMessage(''); try { await action(); setTemporary(''); await cache.invalidateQueries({ queryKey: ['users', account?.id] }); await cache.invalidateQueries({ queryKey: ['role-assignments', account?.id] }); setMessage(apiMode === 'mock' ? `${success} (solo simulación; no cambió el servidor).` : success) } catch (error) { setMessage((error as Error).message) } finally { setBusy(false) } }
  return <section className="stack"><h1>Cuentas y ámbitos</h1>
    {apiMode === 'mock' && <Notice tone="warning">Cuentas de demostración. Las contraseñas temporales y asignaciones no son reales.</Notice>}
    <p>Las personas de reemplazo usan cuentas propias. ADMIN no confirma hechos ni firma por operadores.</p>
    <section className="card stack form"><h2>Crear cuenta</h2><div className="field"><label htmlFor="new-username">Usuario</label><input id="new-username" value={username} onChange={event => setUsername(event.target.value)} autoComplete="off" /></div>
      <div className="field"><label htmlFor="new-name">Nombre</label><input id="new-name" value={name} onChange={event => setName(event.target.value)} /></div>
      <div className="field"><label htmlFor="temporary-password">Contraseña temporal (entregar fuera de SITRAP)</label><input id="temporary-password" type="password" autoComplete="new-password" value={temporary} onChange={event => setTemporary(event.target.value)} /></div>
      <Button disabled={!online || !username.trim() || !name.trim() || (apiMode === 'http' && temporary.length < 12)} busy={busy} onClick={() => void run(async () => { await api.post('/users', apiMode === 'http' ? { id: crypto.randomUUID(), username: username.trim(), name: name.trim(), temporary_password: temporary } : { username: username.trim(), name: name.trim() }); setUsername(''); setName('') }, 'Cuenta creada; cambio de contraseña obligatorio')}>Crear usuario</Button>
    </section>
    <section className="card stack form"><h2>Asignar función</h2><div className="field"><label htmlFor="assign-user">Cuenta</label><select id="assign-user" value={userId} onChange={event => setUserId(event.target.value)}><option value="">Selecciona</option>{users.data?.results.filter(user => user.active).map(user => <option key={user.id} value={user.id}>{user.name}</option>)}</select></div>
      <div className="field"><label htmlFor="assign-role">Rol</label><select id="assign-role" value={role} onChange={event => setRole(event.target.value as Role)}>{(['PRODUCCION', 'TRANSPORTE', 'RECEPCION', 'ADMIN'] as const).map(item => <option key={item} value={item}>{item}</option>)}</select></div>
      {role !== 'ADMIN' && <div className="field"><label htmlFor="assign-location">Ubicación</label><select id="assign-location" value={location} onChange={event => setLocation(event.target.value)}><option value="">Selecciona</option>{locations.data?.results.filter(item => role === 'RECEPCION' ? item.type === 'PUNTO_VENTA' : item.type === 'CENTRO').map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></div>}
      <Button busy={busy} disabled={!online || !userId || (role !== 'ADMIN' && !location)} onClick={() => void run(() => api.post('/role-assignments', { ...(apiMode === 'http' ? { id: crypto.randomUUID(), starts_at: new Date().toISOString() } : {}), user_id: userId, role, scope: role === 'ADMIN' ? 'GLOBAL' : 'UBICACION', location_id: role === 'ADMIN' ? null : location }), 'Asignación guardada')}>Guardar asignación</Button>
    </section>
    {users.isPending && <Notice>Cargando cuentas…</Notice>}{users.isError && <Notice tone="error">No pudimos cargar cuentas.</Notice>}
    {message && <Notice>{message}</Notice>}
    <h2>Usuarios</h2>{users.data?.results.map(user => <article key={user.id} className="card"><h3>{user.name} · @{user.username}</h3><p>{user.active ? 'Activa' : 'Inactiva'} · {user.change_password_required ? 'Debe cambiar contraseña' : 'Acceso configurado'}</p>
      <div className="row"><Button variant="secondary" disabled={!online || busy || user.id === account?.id || (apiMode === 'http' && temporary.length < 12)} onClick={() => void run(async () => { await api.post(`/users/${user.id}/reset-password`, apiMode === 'http' ? { temporary_password: temporary } : {}) }, 'Contraseña temporal restablecida')}>Restablecer contraseña</Button>
        <Button variant="danger" disabled={!online || busy || user.id === account?.id || !user.active} onClick={() => void run(() => api.patch(`/users/${user.id}`, apiMode === 'http' ? { is_active: false } : { active: false }), 'Cuenta desactivada conservando autoría')}>Desactivar</Button></div>
      <ul>{assignments.data?.results.filter(item => item.user_id === user.id).map(item => <li key={item.id}>{item.role} · {item.scope === 'GLOBAL' ? 'Global' : item.location_id} · {item.active ? 'Activa' : 'Inactiva'} {item.active && <Button variant="secondary" disabled={!online || busy} onClick={() => void run(() => api.patch(`/role-assignments/${item.id}`, apiMode === 'http' ? { ends_at: new Date().toISOString() } : { active: false }), 'Asignación terminada')}>Finalizar asignación</Button>}</li>)}</ul>
    </article>)}
  </section>
}
