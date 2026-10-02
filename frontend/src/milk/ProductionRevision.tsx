import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiMode } from '../api/client'
import { createCommand } from '../api/commands'
import { useAuth } from '../auth/AuthProvider'
import { useWorkspace } from '../auth/workspace'
import { getDevice } from '../offline/db'
import { parseLitres, formatLitres } from './draft'
import { Button, Notice } from '../components/ui'

export interface Production { id: string; state: string; center_id: string; date: string; shift_name: string; lock_version: number; version_id: string; total_litres: string; linked_litres: string; details: { animal_id: string; code: string; litres: string }[] }
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
  const query = useQuery({ queryKey: ['milking', account?.id, id], queryFn: () => api.request<Production>(`/milkings/${encodeURIComponent(id!)}`), enabled: !!account && !!id && navigator.onLine })
  const production = query.data
  let proposedTotal: string | null = null
  if (action === 'rectify' && production) {
    try { proposedTotal = formatLitres(production.details.reduce((sum, item) => { const value = parseLitres(values[item.animal_id] ?? item.litres); if (value === null) throw new Error('Dato faltante'); return sum + value }, 0)) } catch { proposedTotal = null }
  }
  async function submit() {
    if (!account || !production || !action || busy || !navigator.onLine || assignment?.role !== 'PRODUCCION') return
    setError(''); setMessage('')
    if (!reason.trim()) { setError('Escribe un motivo obligatorio.'); return }
    setBusy(true)
    try {
      const device = await getDevice(account.id)
      const details = production.details.map(item => { const ml = parseLitres(values[item.animal_id] ?? item.litres); if (ml === null) throw new Error(`Completa los litros de ${item.code}; cero es distinto de vacío.`); return { animal_id: item.animal_id, code: item.code, litres: (ml / 1000).toFixed(3) } })
      if (action === 'rectify' && (details.reduce((sum, item) => sum + Number(item.litres), 0) <= 0 || details.reduce((sum, item) => sum + Number(item.litres), 0) < Number(production.linked_litres))) throw new Error('El total debe ser positivo y cubrir lo ya vinculado a entregas.')
      const command = createCommand({ type: action === 'rectify' ? 'MILKING_RECTIFY' : 'MILKING_VOID', entity_id: production.id, device_id: device.device_id, expected_version: production.lock_version, payload: { reason: reason.trim(), ...(action === 'rectify' ? { new_version_id: crypto.randomUUID(), details } : {}) } })
      // Online-only: server checks linked deliveries and reservations atomically.
      await api.post(`/milkings/${encodeURIComponent(production.id)}/${action}`, command)
      await cache.invalidateQueries({ queryKey: ['milking', account.id, id] })
      await cache.invalidateQueries({ queryKey: ['milkings', account.id] })
      setMessage(apiMode === 'mock' ? 'Cambio simulado en memoria, NO aplicado en SITRAP.' : action === 'rectify' ? 'Rectificación aceptada por el servidor. Las entregas no se modificaron automáticamente.' : 'Producción anulada por el servidor.')
      setAction(null); setReason('')
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  return <section className="stack form"><h1>Producción y versiones</h1>
    {apiMode === 'mock' && <Notice tone="warning">Producción ficticia. La rectificación/anulación aquí es solo demostración.</Notice>}
    {query.isPending && <Notice>Cargando producción…</Notice>}
    {query.isError && <Notice tone="error">No pudimos consultar esta producción o no tienes permiso.</Notice>}
    {production && <article className="card stack"><h2>{production.date} · {production.shift_name}</h2><p>Estado: {production.state} · Versión {production.lock_version} · Documento {production.version_id}</p><p className="quantity">{production.total_litres} L</p><p>Vinculados a entregas: {production.linked_litres} L. Una corrección por vaca no modifica la cantidad aceptada en la entrega.</p>
      <ul>{production.details.map(item => <li key={item.animal_id}>{item.code}: {item.litres} L</li>)}</ul>
      {production.state === 'CONFIRMADA' && assignment?.role === 'PRODUCCION' && <div className="row"><Button variant="secondary" onClick={() => { setValues(Object.fromEntries(production.details.map(item => [item.animal_id, item.litres]))); setAction('rectify') }}>Rectificar litros por vaca</Button><Button variant="danger" onClick={() => setAction('void')}>Anular producción</Button></div>}
    </article>}
    {action && production && <section className="card stack"><h2>{action === 'rectify' ? 'Rectificar litros por vaca' : 'Anular producción'}</h2>
      {action === 'rectify' && production.details.map(item => <div className="field" key={item.animal_id}><label htmlFor={`rectify-${item.animal_id}`}>{item.code} (L)</label><input id={`rectify-${item.animal_id}`} inputMode="decimal" value={values[item.animal_id] ?? item.litres} onChange={event => setValues(previous => ({ ...previous, [item.animal_id]: event.target.value }))} /></div>)}
      {action === 'void' && <Notice tone="warning">No se puede anular si hay entregas publicadas activas o propuestas. El servidor decide con los vínculos actuales, sin forzar.</Notice>}
      <div className="field"><label htmlFor="production-reason">Motivo</label><textarea id="production-reason" value={reason} onChange={event => setReason(event.target.value)} /></div>
      {action === 'rectify' && <p>Versión actual {production.total_litres} L → {proposedTotal ?? 'Revisa los valores por vaca'}. Fecha, turno y centro permanecen fijos.</p>}
      {error && <Notice tone="error">{error}</Notice>}
      <div className="row"><Button busy={busy} onClick={() => void submit()}>{action === 'rectify' ? 'Enviar rectificación' : 'Confirmar anulación'}</Button><Button variant="secondary" onClick={() => setAction(null)}>Volver</Button></div>
    </section>}
    {message && <Notice>{message}</Notice>}
  </section>
}
