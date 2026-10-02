import { useEffect, useState } from 'react'
import { useLiveQuery } from 'dexie-react-hooks'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthProvider'
import { useWorkspace } from '../auth/workspace'
import { apiMode } from '../api/client'
import { createCommand } from '../api/commands'
import { db, enqueue, getDevice, saveCopy } from '../offline/db'
import { syncAccount } from '../offline/sync'
import { useConnection } from '../offline/SyncPanel'
import { useOperationalTransfers, type OperationalTransfer } from './TransportToday'
import { Button, Notice } from '../components/ui'
import { Illustration } from '../components/Illustration'
import { AcceptedMark } from '../components/AcceptedMark'

export function ReceptionToday() {
  const { account } = useAuth()
  const { assignment } = useWorkspace()
  const online = useConnection()
  const query = useOperationalTransfers()
  const cache = useQueryClient()
  const [busy, setBusy] = useState<string | null>(null)
  const [queued, setQueued] = useState<string[]>([])
  const [message, setMessage] = useState('')
  const copies = useLiveQuery(() => account ? db.copies.where('[account_id+kind]').equals([account.id, 'transfer']).toArray() : [], [account?.id], [])
  const operations = useLiveQuery(() => account ? db.events.where('account_id').equals(account.id).toArray() : [], [account?.id], [])
  useEffect(() => { if (query.data && account) void Promise.all(query.data.results.map(item => saveCopy(account.id, 'transfer', item.id, item))).catch(() => setMessage('No se pudieron guardar entregas descargadas.')) }, [query.data, account?.id])
  useEffect(() => { const refresh = () => { if (navigator.onLine && document.visibilityState === 'visible') void query.refetch() }; window.addEventListener('online', refresh); document.addEventListener('visibilitychange', refresh); return () => { window.removeEventListener('online', refresh); document.removeEventListener('visibilitychange', refresh) } }, [query.refetch])
  async function receive(item: OperationalTransfer) {
    if (!account || assignment?.role !== 'RECEPCION' || busy || queued.includes(item.id) || item.correction_pending) return
    setBusy(item.id); setMessage('')
    try {
      const device = await getDevice(account.id)
      const command = createCommand({ type: 'TRANSFER_RECEIVE', entity_id: item.id, device_id: device.device_id, expected_version: item.lock_version, payload: { version_id: item.version_id } })
      await enqueue(account.id, command)
      setQueued(previous => [...previous, item.id])
      if (online && apiMode === 'http') { await syncAccount(account.id); await cache.invalidateQueries({ queryKey: ['operational-transfers', account.id] }) }
      const status = await db.events.get(command.event_id)
      setMessage(status?.status === 'APLICADA' ? 'Recepción física confirmada por el servidor.' : 'Recepción guardada solo en este teléfono. Pendiente de aceptación central.')
    } catch (error) { setMessage((error as Error).message) }
    finally { setBusy(null) }
  }
  const transfers = online ? query.data?.results ?? [] : copies.map(copy => copy.document as OperationalTransfer)
  const underway = transfers.filter(item => item.state === 'EN_CAMINO')
  const received = transfers.filter(item => item.state === 'RECIBIDO')
  return <section className="stack"><h1>Recepciones pendientes</h1>
    {apiMode === 'mock' && <Notice tone="warning">Entregas de demostración. No se registra recepción real ni se envía aviso a producción o transporte.</Notice>}
    <p>Confirma únicamente después de recibir físicamente la leche; leer un aviso o aprobar una corrección son acciones diferentes.</p>
    <Button variant="secondary" disabled={!online} onClick={() => void query.refetch()}>Actualizar recepciones</Button>
    {query.isPending && online && <Notice>Cargando entregas…</Notice>}
    {query.isError && <Notice tone="error">No se pudo consultar el estado actual. Reintenta con conexión.</Notice>}
    {message && <Notice tone={message.startsWith('Recepción física confirmada por el servidor') ? 'success' : 'warning'}>{message.startsWith('Recepción física confirmada por el servidor') ? <AcceptedMark label={message} /> : message}</Notice>}
    {!underway.length && !query.isPending && <div className="card"><Illustration kind="empty" /><p>No tienes recepciones físicas pendientes descargadas.</p></div>}
    {underway.map(item => <article key={item.id} className="card stack"><h2>{item.code}</h2><p>Transporta: {item.driver_name} · Origen: {item.origin_name}</p><p className="quantity">{item.units_presentation} bolsas · {item.units_presentation} L</p>
      {item.correction_pending && <Notice tone="warning">Hay una corrección por aprobar antes de confirmar la recepción. Esta acción permanece bloqueada hasta que termine.</Notice>}
      <Button busy={busy === item.id} disabled={!!item.correction_pending || queued.includes(item.id) || operations.some(op => op.command.type === 'TRANSFER_RECEIVE' && op.command.entity_id === item.id && op.status !== 'RECHAZADA')} onClick={() => void receive(item)}>{busy === item.id ? 'Confirmando…' : 'Confirmar recepción física'}</Button>
    </article>)}
    <h2>Recibidas</h2>{received.length ? received.map(item => <article className="card" key={item.id}>{item.code} · {item.units_presentation} L · Recepción confirmada</article>) : <p>Aún no hay recepciones documentadas.</p>}
  </section>
}
