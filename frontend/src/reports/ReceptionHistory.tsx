import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, apiMode } from '../api/client'
import type { Page } from '../api/types'
import { useAuth } from '../auth/AuthProvider'
import { useConnection } from '../offline/SyncPanel'
import { Button, Notice } from '../components/ui'

interface Reception { id: string; code: string; state: string; units_presentation: number; original_quantity?: number; received_date: string; origin_name: string; destination_name: string }
const defaultDate = () => { const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date()); const get = (type: string) => parts.find(part => part.type === type)?.value; return `${get('year')}-${get('month')}-${get('day')}` }
export function ReceptionHistory() {
  const { account } = useAuth()
  const online = useConnection()
  const [from, setFrom] = useState(`${defaultDate().slice(0, 7)}-01`)
  const [to, setTo] = useState(defaultDate())
  const [applied, setApplied] = useState({ from, to })
  const valid = /^\d{4}-\d{2}-\d{2}$/.test(from) && /^\d{4}-\d{2}-\d{2}$/.test(to) && from <= to
  const query = useQuery({ queryKey: ['reception-history', account?.id, applied.from, applied.to], queryFn: () => api.request<Page<Reception>>(`/transfers?status=RECIBIDO&from=${applied.from}&to=${applied.to}`), enabled: !!account && online })
  return <section className="stack"><h1>Historial de recepciones</h1>
    {apiMode === 'mock' && <Notice tone="warning">Datos de demostración. No hay recepciones físicas reales registradas.</Notice>}
    <div className="row"><div className="field"><label htmlFor="reception-from">Desde</label><input type="date" id="reception-from" value={from} onChange={event => setFrom(event.target.value)} /></div>
      <div className="field"><label htmlFor="reception-to">Hasta</label><input type="date" id="reception-to" value={to} onChange={event => setTo(event.target.value)} /></div>
      <Button disabled={!valid} onClick={() => setApplied({ from, to })}>Filtrar</Button></div>
    {!valid && <Notice tone="error">El período debe tener fechas válidas y Desde no puede superar Hasta.</Notice>}
    {!online && <Notice tone="warning">Necesitas conexión para consultar el historial completo del período.</Notice>}
    {query.isPending && online && <Notice>Cargando recepciones…</Notice>}
    {query.isError && <Notice tone="error">No pudimos consultar el período. <Button variant="secondary" onClick={() => void query.refetch()}>Reintentar</Button></Notice>}
    {query.data?.results.length === 0 && <p>No hay recepciones documentadas en este período.</p>}
    {query.data?.results.map(item => <article className="card" key={item.id}><h2>{item.code} · {item.received_date}</h2><p>{item.origin_name} → {item.destination_name}</p><p className="quantity">{item.units_presentation} L recibidos</p>
      {item.original_quantity !== undefined && item.original_quantity !== item.units_presentation && <p>Valor documental corregido. Original: {item.original_quantity} L; vigente: {item.units_presentation} L. La fecha física no cambió.</p>}
      <Link to={`/entregas/${item.id}`}>Ver detalle e historial</Link></article>)}
    {query.data?.next && <Notice>Hay más recepciones; falta conectar paginación B35.</Notice>}
  </section>
}
