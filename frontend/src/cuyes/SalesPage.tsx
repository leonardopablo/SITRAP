import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { api, apiMode, ApiError } from '../api/client'
import type { Command } from '../api/types'
import { useAuth } from '../auth/AuthProvider'
import { useWorkspace } from '../auth/workspace'
import { Button, Notice } from '../components/ui'
import { useConnection } from '../offline/SyncPanel'
import { allPages } from './actions'
import { commercialCommand, sendCommercial } from './salesActions'
import { SaleCatalog } from './SaleCatalog'
import { NewSaleForm } from './NewSaleForm'
import { SaleDetail } from './SaleDetail'
import type { Candidate, Module, Sale, SalesOptions, SaleType } from './salesTypes'
import type { Shed } from './types'

export function SalesPage() {
  const { account } = useAuth()
  const { assignment } = useWorkspace()
  const role = assignment!.role
  const online = useConnection()
  const cache = useQueryClient()
  const [params, setParams] = useSearchParams()
  const [selected, setSelected] = useState(params.get('orden') ?? '')
  const [tray, setTray] = useState('TODAS')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const pending = useRef<{ fingerprint: string; command: Command } | null>(null)
  const admin = role === 'ADMIN'
  const scope = `workspace=${role}${!admin && assignment?.location_id ? `&center_id=${assignment.location_id}` : ''}`
  const orders = useQuery({
    queryKey: ['sales', account?.id, assignment?.id], enabled: online && !!account && apiMode === 'http',
    queryFn: () => allPages<Sale>(`/cuyes/sales/orders?${scope}`), refetchInterval: 10000,
  })
  const options = useQuery({ queryKey: ['sales-options', account?.id], enabled: online && admin && apiMode === 'http', queryFn: () => api.request<SalesOptions>('/cuyes/sales/options') })
  const modules = useQuery({ queryKey: ['sales-modules', account?.id, role], enabled: online && role !== 'TRANSPORTE' && apiMode === 'http', queryFn: () => allPages<Module>(`/cuyes/sales/modules?workspace=${role}`) })
  const sheds = useQuery({ queryKey: ['sales-sheds', account?.id], enabled: online && role === 'GALPONERO' && apiMode === 'http', queryFn: () => allPages<Shed>('/cuyes/sheds') })
  const order = orders.data?.find(o => o.id === selected)
  const origins = useQuery({ queryKey: ['sales-candidates', account?.id, order?.id, order?.version], enabled: online && role === 'GALPONERO' && !!order && ['PAGADO', 'EN_PREPARACION'].includes(order.state), queryFn: () => allPages<Candidate>(`/cuyes/sales/orders/${order!.id}/candidates?workspace=GALPONERO`) })
  const refresh = () => { void cache.invalidateQueries({ queryKey: ['sales'] }); void cache.invalidateQueries({ queryKey: ['sales-modules'] }); void cache.invalidateQueries({ queryKey: ['sale-availability'] }); void cache.invalidateQueries({ queryKey: ['sales-candidates'] }) }
  function choose(id: string) { setSelected(id); setParams(id ? { orden: id } : {}); setMessage('') }
  async function perform(type: SaleType, payload: Record<string, unknown>, id?: string) {
    setBusy(true); setMessage('')
    try {
      if (!online) throw new Error('Esta etapa requiere conexión.')
      if (!String(payload.reason ?? '').trim()) throw new Error('Escribe el motivo antes de confirmar.')
      const entity = id ?? order?.id
      if (!entity) throw new Error('Selecciona una orden.')
      const fingerprint = JSON.stringify({ type, entity, payload, version: type === 'SALE_CREATE' ? undefined : order?.version })
      if (pending.current && pending.current.fingerprint !== fingerprint) throw new Error('Existe una llamada sin acuse: reintenta la intención guardada antes de cambiar los datos.')
      pending.current ??= { fingerprint, command: await commercialCommand(account!.id, type, entity, payload, type === 'SALE_CREATE' ? undefined : order?.version) }
      const ack = await sendCommercial(pending.current.command)
      pending.current = null; refresh()
      if (type === 'SALE_CREATE') choose(String(ack.result?.order_id))
      setMessage('Operación aceptada por el servidor.'); return true
    } catch (error) {
      if (error instanceof ApiError && error.status > 0 && error.status < 500) pending.current = null
      setMessage((error as Error).message); return false
    } finally { setBusy(false) }
  }
  if (apiMode === 'mock') return <Notice tone="warning">Las ventas requieren Django/PostgreSQL real. No se simulan reservas, pagos ni inventario.</Notice>
  if (!online) return <section className="card"><h1>Ventas de cuyes</h1><Notice tone="warning">Todas las operaciones comerciales y logísticas requieren conexión. El inventario de Etapa 1 conserva sus funciones offline. No se muestran copias de clientes ni pagos sin conexión.</Notice></section>
  const filtered = (orders.data ?? []).filter(o => tray === 'TODAS' || (tray === 'CONFIRMAR' ? ['SOLICITADO', 'VENCIDO', 'AJUSTE_PENDIENTE'].includes(o.state) || o.display_state === 'RESERVA_VENCIDA' : tray === 'PREPARAR' ? ['PAGADO', 'EN_PREPARACION'].includes(o.state) : ['EN_PREPARACION', 'EN_RUTA', 'EN_PUNTO'].includes(o.state)))
  return <section className="stack cuyes-module"><h1>{role === 'TRANSPORTE' ? 'Viajes asignados de cuyes' : 'Ventas y distribución de cuyes'}</h1><Notice>Solo en línea. Solicitar, reservar o pagar no descuenta animales. El Kardex se descuenta una sola vez al confirmar la salida física.</Notice>
    {admin && options.data && <><SaleCatalog modules={modules.data ?? []} onSaved={refresh} /><NewSaleForm key={selected ? 'selected' : 'new'} options={options.data} modules={modules.data ?? []} perform={perform} /></>}
    {role === 'GALPONERO' && <label>Bandeja de trabajo<select aria-label="Bandeja de trabajo" value={tray} onChange={e => setTray(e.target.value)}><option value="TODAS">Todas las órdenes autorizadas</option><option value="CONFIRMAR">Por confirmar</option><option value="PREPARAR">Por preparar</option><option value="DESPACHAR">Por despachar / en distribución</option></select></label>}
    <Button disabled={busy} variant="secondary" onClick={refresh}>Actualizar ventas</Button>
    {orders.isPending && <Notice>Cargando órdenes autorizadas…</Notice>}{orders.isError && <Notice tone="error">{(orders.error as Error).message}</Notice>}
    {message && <Notice>{message}</Notice>}
    {pending.current && !busy && <Button onClick={async () => { setBusy(true); try { await sendCommercial(pending.current!.command); pending.current = null; refresh(); setMessage('Acuse recuperado sin duplicar la operación.') } catch (e) { setMessage((e as Error).message); if (e instanceof ApiError && e.status > 0 && e.status < 500) pending.current = null } finally { setBusy(false) } }}>Reintentar intención guardada con el mismo UUID</Button>}
    <div className="cuy-grid">{filtered.map(o => <button type="button" className="card" key={o.id} onClick={() => choose(o.id)} aria-pressed={o.id === selected}><strong>{o.code}</strong><p>{o.center} · {o.display_state}</p><p>{o.mode === 'DIRECTO' ? 'Recojo directo' : o.point?.name} · {o.lines.reduce((s, l) => s + l.animal_count, 0)} animales</p></button>)}</div>
    {!filtered.length && !orders.isPending && <Notice>No hay órdenes en esta bandeja.</Notice>}
    {role === 'GALPONERO' && order && ['PAGADO', 'EN_PREPARACION'].includes(order.state) && origins.isPending && <Notice>Cargando existencias elegibles y autorizadas para preparar…</Notice>}
    {origins.isError && <Notice tone="error">No se pudieron cargar los orígenes autorizados. Actualiza antes de preparar.</Notice>}
    {order && <SaleDetail key={`${account?.id}:${role}:${order.id}`} accountId={account!.id} order={order} role={role} options={options.data} candidates={origins.data ?? []} shedIds={(sheds.data ?? []).filter(s => s.center_id === order.center_id && s.active).map(s => s.id)} perform={perform} refresh={refresh} />}
  </section>
}
