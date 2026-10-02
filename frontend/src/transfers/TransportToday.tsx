import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthProvider'
import { useWorkspace } from '../auth/workspace'
import { api, apiMode } from '../api/client'
import type { Page } from '../api/types'
import { createCommand } from '../api/commands'
import { db, enqueue, getDevice, saveCopy } from '../offline/db'
import { syncAccount } from '../offline/sync'
import { Button, Notice } from '../components/ui'
import { useConnection } from '../offline/SyncPanel'
import { Illustration } from '../components/Illustration'
import { useLiveQuery } from 'dexie-react-hooks'

export interface OperationalTransfer { id: string; code: string; state: string; lock_version: number; version_id: string; units_presentation: number; origin_name: string; destination_name: string; driver_name: string; receiver_name: string; correction_pending?: boolean }
export function useOperationalTransfers() {
  const { account } = useAuth()
  const { assignment } = useWorkspace()
  const online = useConnection()
  return useQuery({ queryKey: ['operational-transfers', account?.id, assignment?.id], queryFn: () => api.request<Page<OperationalTransfer>>('/transfers'), enabled: !!account && !!assignment && online,
    refetchInterval: () => navigator.onLine && document.visibilityState === 'visible' ? 10000 : false, refetchOnWindowFocus: true })
}
export function TransportToday() {
  const { account } = useAuth()
  const { assignment } = useWorkspace()
  const online = useConnection()
  const query = useOperationalTransfers()
  const cache = useQueryClient()
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [queued, setQueued] = useState<string[]>([])
  const copies = useLiveQuery(() => account ? db.copies.where('[account_id+kind]').equals([account.id, 'transfer']).toArray() : [], [account?.id], [])
  const operations = useLiveQuery(() => account ? db.events.where('account_id').equals(account.id).toArray() : [], [account?.id], [])
  useEffect(() => { if (!query.data || !account) return; void Promise.all(query.data.results.map(item => saveCopy(account.id, 'transfer', item.id, item))).catch(() => setMessage('No se pudieron guardar solicitudes descargadas. No confirmes sin documento local.')) }, [query.data, account?.id])
  useEffect(() => { const refresh = () => { if (navigator.onLine && document.visibilityState === 'visible') void query.refetch() }; window.addEventListener('online', refresh); document.addEventListener('visibilitychange', refresh); return () => { window.removeEventListener('online', refresh); document.removeEventListener('visibilitychange', refresh) } }, [query.refetch])
  async function pickup(item: OperationalTransfer) {
    if (!account || assignment?.role !== 'TRANSPORTE' || busy || queued.includes(item.id)) return
    setBusy(item.id); setMessage('')
    try {
      const device = await getDevice(account.id)
      const command = createCommand({ type: 'TRANSFER_PICKUP', entity_id: item.id, device_id: device.device_id, expected_version: item.lock_version, payload: { version_id: item.version_id } })
      await enqueue(account.id, command)
      setQueued(previous => [...previous, item.id])
      if (online && apiMode === 'http') { await syncAccount(account.id); await cache.invalidateQueries({ queryKey: ['operational-transfers', account.id] }) }
      const status = await db.events.get(command.event_id)
      setMessage(status?.status === 'APLICADA' ? 'Recogida confirmada por el servidor. Recepción verá la entrega.' : 'Confirmación guardada en este teléfono. Pendiente de enviar; recepción todavía no la ve.')
    } catch (error) { setMessage((error as Error).message) }
    finally { setBusy(null) }
  }
  const transfers = online ? query.data?.results ?? [] : copies.map(copy => copy.document as OperationalTransfer)
  const pending = transfers.filter(item => item.state === 'PENDIENTE_RECOGIDA')
  const underway = transfers.filter(item => item.state === 'EN_CAMINO')
  return <section className="stack"><h1>Recogidas de hoy</h1>
    {apiMode === 'mock' && <Notice tone="warning">Entregas de demostración. Tu confirmación solo queda en este teléfono, sin aviso a recepción.</Notice>}
    {query.isPending && online && <Notice>Cargando solicitudes…</Notice>}
    {query.isError && <Notice tone="error">No pudimos actualizar solicitudes. Comprueba la conexión. <Button variant="secondary" onClick={() => void query.refetch()}>Actualizar</Button></Notice>}
    <Button variant="secondary" disabled={!online} onClick={() => void query.refetch()}>Actualizar solicitudes</Button>
    {message && <Notice tone={message.includes('servidor') ? 'success' : 'warning'}>{message}</Notice>}
    {(!query.isPending || !online) && !pending.length && <div className="card"><Illustration kind="empty" /><p>No tienes recogidas pendientes descargadas.</p></div>}
    {pending.map(item => <article className="card stack" key={item.id}><h2>{item.code}</h2><p>{item.origin_name} → {item.destination_name}</p><p className="quantity">{item.units_presentation} bolsas · {item.units_presentation} L</p><p>Versión {item.lock_version}. Confirma solo si estás conforme con la cantidad mostrada; no se vuelve a escribir.</p>
      <Button busy={busy === item.id} disabled={queued.includes(item.id) || operations.some(op => op.command.type === 'TRANSFER_PICKUP' && op.command.entity_id === item.id && op.status !== 'RECHAZADA')} onClick={() => void pickup(item)}>{busy === item.id ? 'Confirmando…' : queued.includes(item.id) || operations.some(op => op.command.type === 'TRANSFER_PICKUP' && op.command.entity_id === item.id && op.status !== 'RECHAZADA') ? 'Recogida registrada o pendiente' : 'Confirmar recogida'}</Button><Link to={`/entregas/${item.id}`}>Ver entrega actual</Link>
    </article>)}
    <h2>En camino</h2>{underway.length ? underway.map(item => <article className="card" key={item.id}><p>{item.code} · {item.units_presentation} L · pendiente de recepción física</p></article>) : <p>No hay entregas en camino.</p>}
  </section>
}
