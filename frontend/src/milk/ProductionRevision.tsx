import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiMode } from '../api/client'
import { createCommand } from '../api/commands'
import { useAuth } from '../auth/AuthProvider'
import { useWorkspace } from '../auth/workspace'
import { db, getDevice, listEvents, readCopy } from '../offline/db'
import { parseLitres, formatLitres } from './draft'
import { Button, Notice } from '../components/ui'

export interface Production { id: string; state: string; center_id: string; date: string; shift_name: string; lock_version: number; version_id: string; total_litres: string; linked_litres: string | null; details: { animal_id: string; code: string; litres: string }[] }
const todayLima = () => { const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date()); const get = (key: string) => parts.find(part => part.type === key)?.value ?? ''; return `${get('year')}-${get('month')}-${get('day')}` }
export function ProductionRevision() {
  const { id } = useParams()
  const { account } = useAuth()
  const { assignment } = useWorkspace()
  const cache = useQueryClient()
  const [action, setAction] = useState<'rectify' | 'void' | null>(null)
  const [values, setValues] = useState<Record<string, string>>({})
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [reviewConfirm, setReviewConfirm] = useState(false)
  const query = useQuery({ queryKey: ['milking', account?.id, id], queryFn: () => api.request<Production>(`/milkings/${encodeURIComponent(id!)}`), enabled: !!account && !!id && navigator.onLine })
  const production = query.data
  const canConfirm = production?.state === 'BORRADOR' && production.date === todayLima() && production.details.length > 0 && production.details.every(item => item.litres !== null && item.litres !== undefined) && Number(production.total_litres) > 0
  let proposedTotal: string | null = null
  if (action === 'rectify' && production) {
    try { proposedTotal = formatLitres(production.details.reduce((sum, item) => { const value = parseLitres(values[item.animal_id] ?? item.litres); if (value === null) throw new Error('Dato faltante'); return sum + value }, 0)) } catch { proposedTotal = null }
  }
  async function submit() {
    if (!account || !production || !action || busy || !navigator.onLine || assignment?.role !== 'PRODUCCION' || assignment.location_id !== production.center_id) return
    setError(''); setMessage('')
    if (!reason.trim()) { setError('Escribe un motivo obligatorio.'); return }
    setBusy(true)
    try {
      if (action === 'void' && production.state === 'BORRADOR' && (await listEvents(account.id)).some(entry => entry.command.entity_id === production.id && !['APLICADA', 'RECHAZADA'].includes(entry.status))) throw new Error('Hay operaciones de este borrador pendientes en el teléfono. Sincroniza primero y vuelve a consultar el historial.')
      const device = await getDevice(account.id)
      const details = action === 'rectify' ? production.details.map(item => { const ml = parseLitres(values[item.animal_id] ?? item.litres); if (ml === null) throw new Error(`Completa los litros de ${item.code}; cero es distinto de vacío.`); return { animal_id: item.animal_id, code: item.code, litres: (ml / 1000).toFixed(3) } }) : []
      if (action === 'rectify' && (details.reduce((sum, item) => sum + Number(item.litres), 0) <= 0 || (production.linked_litres !== null && details.reduce((sum, item) => sum + Number(item.litres), 0) < Number(production.linked_litres)))) throw new Error('El total debe ser positivo y cubrir lo ya vinculado a entregas.')
      const command = createCommand({ type: action === 'rectify' ? 'MILKING_RECTIFY' : 'MILKING_VOID', entity_id: production.id, device_id: device.device_id, expected_version: production.lock_version, payload: { reason: reason.trim(), ...(action === 'rectify' ? apiMode === 'http' ? { version_id: crypto.randomUUID(), details: details.map(item => ({ animal_id: item.animal_id, liters: item.litres })) } : { new_version_id: crypto.randomUUID(), details } : {}) } })
      // Online-only: server checks linked deliveries and reservations atomically.
      await api.post(`/milkings/${encodeURIComponent(production.id)}/${action}`, command)
      let localWarning = ''
      if (action === 'void' && production.state === 'BORRADOR' && assignment.location_id) {
        try {
          const copy = await readCopy(account.id, 'milking-draft', assignment.location_id)
          if (copy && (copy.document as { id?: string }).id === production.id) await db.copies.delete(copy.key)
        } catch { localWarning = ' No se pudo limpiar la copia de este teléfono; no vuelvas a enviarla.' }
      }
      await cache.invalidateQueries({ queryKey: ['milking', account.id, id] })
      await cache.invalidateQueries({ queryKey: ['milkings', account.id] })
      setMessage((apiMode === 'mock' ? 'Cambio simulado en memoria, NO aplicado en SITRAP.' : action === 'rectify' ? 'Rectificación aceptada por el servidor. Las entregas no se modificaron automáticamente.' : production.state === 'BORRADOR' ? 'Borrador descartado. La auditoría se conserva; no se creó ningún lote.' : 'Producción anulada por el servidor.') + localWarning)
      setAction(null); setReason('')
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  async function confirmExisting() {
    if (!account || !production || !canConfirm || !reviewConfirm || busy || !navigator.onLine || assignment?.role !== 'PRODUCCION' || assignment.location_id !== production.center_id) return
    setError(''); setMessage(''); setBusy(true)
    try {
      if ((await listEvents(account.id)).some(entry => entry.command.entity_id === production.id && !['APLICADA', 'RECHAZADA'].includes(entry.status))) throw new Error('Hay operaciones de esta producción pendientes en este dispositivo. Sincroniza antes de confirmar desde el historial.')
      const device = await getDevice(account.id)
      const command = createCommand({ type: 'MILKING_CONFIRM', entity_id: production.id, device_id: device.device_id, expected_version: production.lock_version, payload: { version_id: production.version_id, lot_id: crypto.randomUUID() } })
      await api.post(`/milkings/${encodeURIComponent(production.id)}/confirm`, command)
      await cache.invalidateQueries({ queryKey: ['milking', account.id, id] })
      await cache.invalidateQueries({ queryKey: ['milkings', account.id] })
      await cache.invalidateQueries({ queryKey: ['lots', account.id] })
      setReviewConfirm(false)
      setMessage(apiMode === 'mock' ? 'Confirmación simulada; no se creó un lote real.' : 'Producción confirmada por el servidor. El lote ya puede consultarse en Preparar entrega.')
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  return <section className="stack form"><h1>Producción y versiones</h1>
    {apiMode === 'mock' && <Notice tone="warning">Producción ficticia. La rectificación/anulación aquí es solo demostración.</Notice>}
    {query.isPending && <Notice>Cargando producción…</Notice>}
    {query.isError && <Notice tone="error">No pudimos consultar esta producción o no tienes permiso.</Notice>}
    {production && <article className="card stack"><h2>{production.date} · {production.shift_name}</h2><p>Estado: {production.state} · Versión {production.lock_version} · Documento {production.version_id}</p><p className="quantity">{production.total_litres} L</p><p>{production.linked_litres === null ? 'El servidor valida las cantidades ya vinculadas.' : `Vinculados a entregas: ${production.linked_litres} L.`} Una corrección por vaca no modifica la cantidad aceptada en la entrega.</p>
      <ul>{production.details.map(item => <li key={item.animal_id}>{item.code}: {item.litres} L</li>)}</ul>
      {production.state === 'CONFIRMADA' && assignment?.role === 'PRODUCCION' && <div className="row"><Button variant="secondary" onClick={() => { setValues(Object.fromEntries(production.details.map(item => [item.animal_id, item.litres]))); setAction('rectify') }}>Rectificar litros por vaca</Button><Button variant="danger" onClick={() => setAction('void')}>Anular producción</Button></div>}
      {production.state === 'BORRADOR' && assignment?.role === 'PRODUCCION' && assignment.location_id === production.center_id && <><Button variant="secondary" onClick={() => setReviewConfirm(true)}>Revisar y confirmar producción</Button><Button variant="danger" onClick={() => setAction('void')}>Descartar borrador</Button></>}
    </article>}
    {reviewConfirm && production?.state === 'BORRADOR' && <section className="card stack"><h2>Confirmar producción existente</h2><p>Centro: {production.center_id} · Fecha: {production.date} · Turno: {production.shift_name}</p><ul>{production.details.map(item => <li key={item.animal_id}>{item.code}: {item.litres ?? 'Sin dato'} L</li>)}</ul><p className="quantity">Total: {production.total_litres} L</p>
      {!canConfirm && <Notice tone="warning">Solo se puede confirmar el ordeño de hoy en Perú, con todas las vacas completas y un total positivo.</Notice>}
      <div className="row"><Button busy={busy} disabled={!canConfirm || !navigator.onLine} onClick={() => void confirmExisting()}>Confirmar producción</Button><Button variant="secondary" onClick={() => setReviewConfirm(false)}>Volver</Button></div></section>}
    {action && production && <section className="card stack"><h2>{action === 'rectify' ? 'Rectificar litros por vaca' : production.state === 'BORRADOR' ? 'Descartar borrador' : 'Anular producción'}</h2>
      {action === 'rectify' && production.details.map(item => <div className="field" key={item.animal_id}><label htmlFor={`rectify-${item.animal_id}`}>{item.code} (L)</label><input id={`rectify-${item.animal_id}`} inputMode="decimal" value={values[item.animal_id] ?? item.litres} onChange={event => setValues(previous => ({ ...previous, [item.animal_id]: event.target.value }))} /></div>)}
      {action === 'void' && <Notice tone="warning">{production.state === 'BORRADOR' ? 'El borrador quedará anulado en el historial, no se borrará la auditoría ni se creará un lote. Sincroniza antes cualquier operación pendiente de este ordeño.' : 'No se puede anular si hay entregas publicadas activas o propuestas. El servidor decide con los vínculos actuales, sin forzar.'}</Notice>}
      <div className="field"><label htmlFor="production-reason">Motivo</label><textarea id="production-reason" value={reason} onChange={event => setReason(event.target.value)} /></div>
      {action === 'rectify' && <p>Versión actual {production.total_litres} L → {proposedTotal ?? 'Revisa los valores por vaca'}. Fecha, turno y centro permanecen fijos.</p>}
      {error && <Notice tone="error">{error}</Notice>}
      <div className="row"><Button busy={busy} onClick={() => void submit()}>{action === 'rectify' ? 'Enviar rectificación' : production.state === 'BORRADOR' ? 'Confirmar descarte' : 'Confirmar anulación'}</Button><Button variant="secondary" onClick={() => setAction(null)}>Volver</Button></div>
    </section>}
    {message && <Notice>{message}</Notice>}
  </section>
}
