import { useCallback, useEffect, useState } from 'react'
import { useLiveQuery } from 'dexie-react-hooks'
import { apiMode } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { db, listEvents } from './db'
import { applyChanges, prepareAccount } from './prepare'
import { syncAccount } from './sync'
import { Button, Notice } from '../components/ui'
import { Link } from 'react-router-dom'

export function useConnection() {
  const [online, setOnline] = useState(navigator.onLine)
  useEffect(() => { const update = () => setOnline(navigator.onLine); window.addEventListener('online', update); window.addEventListener('offline', update); return () => { window.removeEventListener('online', update); window.removeEventListener('offline', update) } }, [])
  return online
}
const labels = { PENDIENTE: 'Pendiente de enviar', ENVIANDO: 'Enviando', APLICADA: 'Aceptado por el sistema', REQUIERE_SESION: 'Necesita ingresar', ESPERA_DEPENDENCIA: 'Espera un registro anterior', RECHAZADA: 'Rechazado; necesita revisión' }
export function SyncStatus() {
  const { account } = useAuth()
  const online = useConnection()
  const count = useLiveQuery(async () => (await listEvents(account!.id)).filter(item => !['APLICADA', 'RECHAZADA'].includes(item.status)).length, [account?.id], 0)
  return <Link to="/sincronizacion" className="badge" aria-label={`${online ? 'Con conexión' : 'Sin conexión'}, ${count} operaciones pendientes`}>{online ? 'Con conexión' : 'Sin conexión'} · {count} pendientes</Link>
}
export function SyncPanel() {
  const { account } = useAuth()
  const online = useConnection()
  const events = useLiveQuery(() => listEvents(account!.id), [account?.id], [])
  const device = useLiveQuery(() => db.devices.get(account!.id), [account?.id])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const refresh = useCallback(async () => {
    if (!account || !online || apiMode !== 'http') return
    try { await applyChanges(account.id) } catch { /* explicit preparation required if cursor expired */ }
    try { await syncAccount(account.id) } catch (error) { setMessage((error as Error).message) }
  }, [account?.id, online])
  useEffect(() => { void refresh(); const onFocus = () => void refresh(); window.addEventListener('focus', onFocus); window.addEventListener('online', onFocus); return () => { window.removeEventListener('focus', onFocus); window.removeEventListener('online', onFocus) } }, [refresh])
  async function run(action: () => Promise<unknown>, success: string) { setBusy(true); setMessage(''); try { await action(); setMessage(success) } catch (error) { setMessage((error as Error).message) } finally { setBusy(false) } }
  return <section className="stack"><h1>Pendientes de sincronización</h1>
    <p><Link to="/notas">Notas provisionales</Link> (separadas de las operaciones que espera el servidor).</p>
    {apiMode === 'mock' && <Notice tone="warning">Modo simulado. Puedes preparar copias vacías de demostración, pero no existe servidor para confirmar registros. Sincronizar está deshabilitado.</Notice>}
    <Notice>{online ? 'Con conexión' : 'Sin conexión'} · Preparación: {device?.prepared_until ? new Intl.DateTimeFormat('es-PE', { dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Lima' }).format(new Date(device.prepared_until)) : 'no preparada'} · {events?.filter(item => item.status !== 'APLICADA' && item.status !== 'RECHAZADA').length ?? 0} pendientes</Notice>
    <div className="row"><Button disabled={!online} busy={busy} onClick={() => run(() => prepareAccount(account!.id), 'Datos preparados en este teléfono. No son confirmaciones de negocio.')}>Preparar dispositivo</Button>
      <Button variant="secondary" busy={busy} disabled={!online || apiMode !== 'http' || !device?.registered} onClick={() => run(async () => { await applyChanges(account!.id); await syncAccount(account!.id) }, 'Actualización terminada; comprueba los estados individuales.')}>Sincronizar ahora</Button></div>
    {message && <Notice>{message}</Notice>}
    {!events?.length && <p>No hay operaciones locales.</p>}
    {events?.map(entry => <article className="card" key={entry.event_id}><h2>{entry.command.type.replaceAll('_', ' ')}</h2><p><strong>{labels[entry.status]}</strong> · {new Intl.DateTimeFormat('es-PE', { dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Lima' }).format(new Date(entry.created_at))}</p>
      <p className="help">Evento {entry.event_id}</p>{entry.error && <Notice tone={entry.status === 'RECHAZADA' ? 'error' : 'warning'}>{entry.error.message}</Notice>}
      {entry.status === 'RECHAZADA' && <p>Conservado para revisión. No se reenviará automáticamente ni se forzará su aceptación.</p>}
    </article>)}
  </section>
}
