import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, apiMode } from '../api/client'
import type { Page } from '../api/types'
import { useAuth } from '../auth/AuthProvider'
import { useConnection } from '../offline/SyncPanel'
import { Button, Notice } from '../components/ui'

interface LotItem { id: string; code: string; date: string; quantity: string; production_state: string }
interface Milestone { at: string; registered_at: string; actor_name: string }
interface Journey {
  id: string; code: string; state: string; quantity: string | null
  origin_name: string; destination_name: string; driver_name: string; receiver_name: string
  request_at: string | null; pickup: Milestone | null; reception: Milestone | null
  travel_minutes: number | null; inconsistent_time: boolean; has_history: boolean
}
interface Trace {
  lot: { id: string; code: string; production_id: string; state: string; date: string; confirmed_at: string | null; center_name: string; turn_name: string; responsible_name: string; quantity: string }
  transfers: Journey[]; count: number; draft_count: number; next_offset: number | null
}
const dateTime = (value: string | null) => value ? new Intl.DateTimeFormat('es-PE', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Lima' }).format(new Date(value)) : 'Aún no registrado'
const duration = (minutes: number) => minutes >= 60 ? `${Math.floor(minutes / 60)} h ${minutes % 60} min` : `${minutes} min`
const stateLabels: Record<string, string> = { BORRADOR: 'Borrador', PENDIENTE_RECOGIDA: 'Pendiente de recogida', EN_CAMINO: 'En camino', RECIBIDO: 'Recibido', CANCELADO: 'Cancelado' }

function MilestoneCard({ number, title, at, actor, muted = false }: { number: string; title: string; at: string | null; actor?: string; muted?: boolean }) {
  return <li className={`trace-step${muted ? ' trace-step--muted' : ''}`}><span className="trace-step__number" aria-hidden="true">{number}</span>
    <div><strong>{title}</strong><time dateTime={at ?? undefined}>{dateTime(at)}</time>{actor && <span className="help">Por {actor}</span>}</div>
  </li>
}

function JourneyCard({ journey, index }: { journey: Journey; index: number }) {
  return <article className="trace-journey" aria-labelledby={`journey-${journey.id}`}>
    <div className="trace-journey__heading"><div><span className="trace-eyebrow">Ruta {String(index + 1).padStart(2, '0')}</span><h3 id={`journey-${journey.id}`}>{journey.origin_name} <span aria-hidden="true">→</span> {journey.destination_name}</h3><p className="help">Entrega {journey.code} · {journey.quantity === null ? 'Lote no vigente en esta versión' : `${journey.quantity} L vinculados`}</p></div><span className={`trace-state trace-state--${journey.state.toLowerCase()}`}>{stateLabels[journey.state] ?? journey.state}</span></div>
    <ol className="trace-steps" aria-label={`Etapas de la entrega ${journey.code}`}>
      <MilestoneCard number="01" title="Solicitud enviada" at={journey.request_at} muted={!journey.request_at} />
      <MilestoneCard number="02" title="Leche recogida" at={journey.pickup?.at ?? null} actor={journey.pickup?.actor_name ?? journey.driver_name} muted={!journey.pickup} />
      <MilestoneCard number="03" title="Leche recibida" at={journey.reception?.at ?? null} actor={journey.reception?.actor_name ?? journey.receiver_name} muted={!journey.reception} />
    </ol>
    <div className="trace-journey__foot"><p><strong>Tiempo entre recogida y recepción:</strong> {journey.inconsistent_time ? 'No calculable: horas registradas incoherentes' : journey.travel_minutes === null ? 'Pendiente de ambas confirmaciones' : duration(journey.travel_minutes)}</p><p className="help">Conductor: {journey.driver_name} · Receptor: {journey.receiver_name}</p>
      {(journey.pickup || journey.reception) && <p className="help">Las horas de los pasos corresponden al hecho declarado; puede haberse sincronizado después. No es seguimiento GPS ni tiempo exacto de conducción.</p>}
      {journey.has_history && <p className="help">Esta entrega tuvo revisiones o correcciones; la cantidad mostrada corresponde al documento vigente.</p>}
      <Link to={`/entregas/${journey.id}`}>Ver documento de entrega</Link>
    </div>
  </article>
}

function LotDirectory() {
  const { account } = useAuth()
  const online = useConnection()
  const [search, setSearch] = useState('')
  const [code, setCode] = useState('')
  const [offset, setOffset] = useState(0)
  const lots = useQuery({ queryKey: ['admin-lots', account?.id, code, offset], queryFn: () => api.request<Page<LotItem>>(`/lots?${new URLSearchParams({ code, limit: '20', offset: String(offset) })}`), enabled: !!account && online && apiMode === 'http' })
  return <section className="stack trace-page"><div className="trace-hero"><span className="trace-eyebrow">SITRAP · Trazabilidad</span><h1>La historia de cada lote</h1><p>Del ordeño a la recepción, sin perder de vista a las personas ni las horas registradas.</p><span className="trace-hero__art" aria-hidden="true">◌</span></div>
    <form className="trace-search card" onSubmit={event => { event.preventDefault(); setOffset(0); setCode(search.trim()) }}><div className="field"><label htmlFor="trace-search">Buscar por código de lote</label><input id="trace-search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Ej. L-20261009" /></div><Button type="submit">Buscar lote</Button></form>
    {!online && <Notice tone="warning">Conéctate para consultar datos actuales de trazabilidad.</Notice>}
    {apiMode === 'mock' && <Notice tone="warning">La trazabilidad oficial solo está disponible con la API real.</Notice>}
    {lots.isPending && online && apiMode === 'http' && <Notice>Cargando lotes…</Notice>}
    {lots.isError && <Notice tone="error">No se pudieron consultar los lotes. <Button variant="secondary" onClick={() => void lots.refetch()}>Reintentar</Button></Notice>}
    {lots.data && <><p className="help">{lots.data.count} {lots.data.count === 1 ? 'lote encontrado' : 'lotes encontrados'} · página {Math.floor(offset / 20) + 1}</p>
      <div className="trace-directory">{lots.data.results.map(lot => <Link className="trace-lot-card" key={lot.id} to={`/administracion/lotes/${lot.id}`}><span className="trace-lot-card__icon" aria-hidden="true">◉</span><span><strong>{lot.code}</strong><small>{lot.date} · {lot.quantity} L · {lot.production_state}</small></span><span aria-hidden="true">↗</span></Link>)}</div>
      {lots.data.results.length === 0 && <Notice>No hay lotes para esta búsqueda. Prueba otro código.</Notice>}
      <div className="row">{offset > 0 && <Button variant="secondary" onClick={() => setOffset(Math.max(0, offset - 20))}>Anterior</Button>}{lots.data.next && <Button variant="secondary" onClick={() => setOffset(offset + 20)}>Siguiente</Button>}</div></>}
  </section>
}

function LotTraceDetail({ id }: { id: string }) {
  const { account } = useAuth()
  const online = useConnection()
  const [offset, setOffset] = useState(0)
  const query = useQuery({ queryKey: ['lot-trace', account?.id, id, offset], queryFn: () => api.request<Trace>(`/lots/${encodeURIComponent(id)}/trace?${new URLSearchParams({ limit: '20', offset: String(offset) })}`), enabled: !!account && online && apiMode === 'http' })
  const data = query.data
  return <section className="stack trace-page"><Link to="/administracion/lotes">← Volver a los lotes</Link>
    {query.isPending && online && apiMode === 'http' && <Notice>Cargando recorrido…</Notice>}
    {query.isError && <Notice tone="error">No se pudo consultar este lote o ya no tienes permiso. <Button variant="secondary" onClick={() => void query.refetch()}>Reintentar</Button></Notice>}
    {!online && <Notice tone="warning">Conéctate para consultar el recorrido actual.</Notice>}
    {data && <><div className="trace-hero"><span className="trace-eyebrow">Origen verificado · {data.lot.state}</span><h1>Lote {data.lot.code}</h1><p>{data.lot.center_name} · {data.lot.turn_name} · {data.lot.date}</p><span className="trace-hero__art" aria-hidden="true">◌</span></div>
      <section className="trace-origin card" aria-labelledby="trace-origin-title"><div className="trace-origin__icon" aria-hidden="true">01</div><div><span className="trace-eyebrow">El origen</span><h2 id="trace-origin-title">Producción de leche</h2><p>Responsable: <strong>{data.lot.responsible_name}</strong></p><p>Confirmación: {dateTime(data.lot.confirmed_at)}</p><p className="help">Fecha de ordeño: {data.lot.date} · Centro: {data.lot.center_name}</p></div><p className="trace-origin__quantity">{data.lot.quantity} <span>L producidos</span></p></section>
      <div className="trace-divider"><span aria-hidden="true">↓</span><p>Un lote puede distribuirse en varias entregas</p></div>
      <div className="row"><h2>Recorrido de las entregas</h2><span className="badge">{data.count} {data.count === 1 ? 'entrega' : 'entregas'}</span></div>
      {data.draft_count > 0 && <Notice tone="warning">{data.draft_count} {data.draft_count === 1 ? 'borrador de entrega no enviado' : 'borradores de entrega no enviados'}: no son rutas ni tienen recogida o recepción. Se conservan en el sistema, pero no se dibujan como recorridos.</Notice>}
      {data.transfers.length === 0 && <Notice>Este lote aún no tiene solicitudes enviadas a transporte.</Notice>}
      <div className="trace-journeys">{data.transfers.map((journey, index) => <JourneyCard key={journey.id} journey={journey} index={offset + index} />)}</div>
      <div className="row">{offset > 0 && <Button variant="secondary" onClick={() => setOffset(Math.max(0, offset - 20))}>Entregas anteriores</Button>}{data.next_offset !== null && <Button variant="secondary" onClick={() => setOffset(data.next_offset!)}>Más entregas</Button>}</div>
    </>}
  </section>
}

export function LotTracePage() {
  const { id } = useParams()
  return id ? <LotTraceDetail key={id} id={id} /> : <LotDirectory />
}
