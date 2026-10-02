import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, apiMode } from '../api/client'
import type { Page } from '../api/types'
import { useAuth } from '../auth/AuthProvider'
import { Button, Notice } from '../components/ui'
import { useConnection } from '../offline/SyncPanel'
import type { MilkMetrics } from './milk'
import type { TransferMetrics } from './calendar'

interface CatalogOption { id: string; name: string; type?: string }
export function AdminOverview() {
  const { account } = useAuth()
  const online = useConnection()
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [center, setCenter] = useState('')
  const [product, setProduct] = useState('')
  const [period, setPeriod] = useState<{ from: string; to: string; center: string; product: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const valid = /^\d{4}-\d{2}-\d{2}$/.test(from) && /^\d{4}-\d{2}-\d{2}$/.test(to) && from <= to
  const locations = useQuery({ queryKey: ['admin-locations', account?.id], queryFn: () => api.request<Page<CatalogOption>>('/locations'), enabled: !!account && online })
  const products = useQuery({ queryKey: ['admin-products', account?.id], queryFn: () => api.request<Page<CatalogOption>>('/products'), enabled: !!account && online })
  const params = new URLSearchParams({ from: period?.from ?? '', to: period?.to ?? '', ...(period?.center ? { center_id: period.center } : {}), ...(period?.product ? { product_id: period.product } : {}) })
  const milk = useQuery({ queryKey: ['admin-milk', account?.id, period], queryFn: () => api.request<MilkMetrics>(`/metrics/milk?${params}`), enabled: !!account && online && !!period })
  const transfers = useQuery({ queryKey: ['admin-transfers', account?.id, period], queryFn: () => api.request<TransferMetrics>(`/metrics/transfers?${params}`), enabled: !!account && online && !!period })
  async function download() {
    if (!period || !online || apiMode !== 'http' || busy) return
    setBusy(true); setError('')
    try {
      const blob = await api.pdf(`/reports/overview.pdf?${params}`)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = `sitrap-resumen-${period.from}-${period.to}.pdf`; anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  const picked = transfers.data?.days.reduce((sum, day) => sum + Number(day.picked_litres), 0) ?? 0
  const received = transfers.data?.days.reduce((sum, day) => sum + Number(day.received_litres), 0) ?? 0
  return <section className="stack"><h1>Resumen administrativo</h1>
    {apiMode === 'mock' && <Notice tone="warning">Resumen ficticio. No representa datos globales ni se puede descargar un PDF oficial.</Notice>}
    <p>ADMIN consulta y gestiona ámbitos, pero no confirma recogidas, recepciones ni aprobaciones por otra persona.</p>
    <div className="row"><div className="field"><label htmlFor="admin-from">Desde</label><input id="admin-from" type="date" value={from} onChange={event => setFrom(event.target.value)} /></div><div className="field"><label htmlFor="admin-to">Hasta</label><input id="admin-to" type="date" value={to} onChange={event => setTo(event.target.value)} /></div></div>
    <div className="row"><div className="field"><label htmlFor="admin-center">Centro</label><select id="admin-center" value={center} onChange={event => setCenter(event.target.value)}><option value="">Todos</option>{locations.data?.results.filter(item => item.type === 'CENTRO').map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></div>
      <div className="field"><label htmlFor="admin-product">Producto</label><select id="admin-product" value={product} onChange={event => setProduct(event.target.value)}><option value="">Todos</option>{products.data?.results.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></div></div>
    <Button disabled={!valid || !online} onClick={() => setPeriod({ from, to, center, product })}>Consultar resumen</Button>
    {period && (milk.isPending || transfers.isPending) && <Notice>Cargando métricas…</Notice>}
    {(milk.isError || transfers.isError || locations.isError || products.isError) && <Notice tone="error">No se pudieron consultar todos los datos del resumen. Reintenta con conexión.</Notice>}
    {period && milk.data && transfers.data && <><p>Período: {period.from} a {period.to}. Cortes del servidor: producción {milk.data.cutoff_at}, entregas {transfers.data.cutoff_at} ({transfers.data.time_zone}).</p>
      <div className="row"><div className="card">Producción: <strong>{milk.data.total_litres} L</strong></div><div className="card">Recogido: <strong>{picked.toLocaleString('es-PE')} L</strong></div><div className="card">Recibido: <strong>{received.toLocaleString('es-PE')} L</strong></div></div>
      <p>Son medidas separadas, no sumables como una única cantidad.</p><Button disabled={apiMode !== 'http' || !online} busy={busy} onClick={() => void download()}>Descargar resumen PDF</Button></>}
    {error && <Notice tone="error">{error}</Notice>}
    <div className="row"><Link to="/correcciones">Consultar correcciones</Link></div>
  </section>
}
