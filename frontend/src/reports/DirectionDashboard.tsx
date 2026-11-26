import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { Notice } from '../components/ui'
import { limaToday } from '../cuyes/types'

type CuyMonth = { population: number; births: number; deaths: number; weaned: number }
type Cuyes = {
  population: number; births: number; stillborn: number; deaths: number; weaned: number
  birth_rate: number | null; mortality_rate: number | null; stillborn_rate: number | null; average_population: number | null
  moved: number; dispatched: number; received: number; adjusted: number; reclassified: number; pending_counts: number; alerts: number
  monthly: Record<string, CuyMonth>
  pens: { code: string; shed: string; purpose: string; population: number; capacity: number; composition: { category: string; quality: string; quantity: number }[] }[]
  sales: { pending: number; delivered: number; expired: number; dispatched_units: number; validated_payments: Record<string, string> }
  trace: { code: string; state: string; mode: string; point: string | null; registered_at: string; dispatched_at: string | null
    origins: { shed: string; pen: string; lot: string; category: string; quality: string; quantity: number }[]
    delivery: { stage: string; performed_by: string; registered_by: string; time: string }[] }[]
}
type Milk = {
  milkings: number; liters: string; monthly: Record<string, string>; turns: Record<string, string>
  cows: { code: string; name: string; liters: string | null; records: number }[]
  sent: string; received: string; reception_difference: string; pending: number
  trace: { code: string; state: string; destination: string; driver: string; requested: string | null;
    pickup: string | null; reception: string | null; planned: string; sent: string | null; received: string | null
    lots: { code: string; date: string; liters: string }[] }[]
}
type Center = { id: string; name: string }
type Report = { demo: boolean; refreshed_at: string; centers: Center[]; results: (Center & {
  milk: Milk | null; cuyes: Cuyes | null
  activity: { id: string; name: string; milkings: number; milk_liters: string; milk_pickups: number; milk_receptions: number; cuy_records: number; cuy_pickups: number }[]
})[] }
const num = (n: number | string) => Number(n).toLocaleString('es-PE', { maximumFractionDigits: 3 })
const time = (value: string | null) => value ? new Date(value).toLocaleString('es-PE', { timeZone: 'America/Lima' }) : 'Pendiente'
const pct = (value: number | null) => value === null ? 'Sin datos suficientes' : `${num(value)} %`
const label = (value: string) => ({ RECOGIDA_ORIGEN: 'Recogida en origen', LLEGADA_PUNTO: 'Llegada al punto', ENTREGA_CLIENTE: 'Entrega al cliente',
  EN_PUNTO: 'En punto de venta', EN_RUTA: 'En ruta', DIRECTO: 'Recojo directo', PUNTO: 'Traslado a punto de venta',
} as Record<string, string>)[value] ?? value.toLowerCase().replaceAll('_', ' ')

function Bars({ title, values }: { title: string; values: Record<string, number | string> }) {
  const max = Math.max(1, ...Object.values(values).map(Number))
  return <figure className="direction-chart"><figcaption><strong>{title}</strong></figcaption>
    {Object.entries(values).length ? <ul>{Object.entries(values).map(([key, value]) => <li key={key}>
      <span>{key}</span><meter min={0} max={max} value={Math.max(0, Number(value))} aria-label={`${title}: ${key}`} /><span>{num(value)}</span>
    </li>)}</ul> : <p>Sin registros en el período.</p>}
  </figure>
}

export function DirectionDashboard() {
  const { account } = useAuth()
  const today = limaToday()
  const [start, setStart] = useState(`${today.slice(0, 4)}-01-01`)
  const [end, setEnd] = useState(today)
  const [center, setCenter] = useState('')
  const valid = !!start && !!end && start <= end && end <= today
  const params = new URLSearchParams({ start, end, ...(center ? { center_id: center } : {}) })
  const query = useQuery({ queryKey: ['direction', account?.id, params.toString()], enabled: !!account && valid,
    queryFn: () => api.request<Report>(`/direction/dashboard?${params}`), refetchInterval: 60_000, retry: false })
  return <section className="stack direction">
    <h1>Dirección DIPROBSA</h1><p>Indicadores y trazabilidad de solo lectura. Los pendientes reflejan el estado actual; las cifras de actividad corresponden al período elegido.</p>
    <div className="card row">
      <label>Desde<input type="date" max={end || today} value={start} onChange={e => setStart(e.target.value)} /></label>
      <label>Hasta<input type="date" min={start} max={today} value={end} onChange={e => setEnd(e.target.value)} /></label>
      <label>Centro<select aria-label="Centro" value={center} onChange={e => setCenter(e.target.value)}>
        <option value="">Todos los centros</option>{query.data?.centers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select></label>
      <button className="button secondary" disabled={!valid || query.isFetching} onClick={() => void query.refetch()}>Actualizar indicadores</button>
    </div>
    {!valid && <Notice tone="warning">Selecciona un rango de fechas válido.</Notice>}
    {valid && query.isPending && <Notice>Cargando indicadores…</Notice>}
    {query.isError && <Notice tone="error">{query.error.message}</Notice>}
    {query.data?.demo && <Notice tone="warning">Datos ficticios de demostración. No representan actividad real del personal.</Notice>}
    {query.data && <p>Actualizado: {time(query.data.refreshed_at)}</p>}
    {query.data?.results.map(c => <section className="card stack" key={c.id}>
      <h2>{c.name}</h2>
      <h3>Vacas y leche</h3>
      {c.milk ? <MilkSection data={c.milk} /> : <p>No aplica: sin actividad ni configuración de leche.</p>}
      <h3>Cuyes y ventas</h3>
      {c.cuyes ? <CuySection data={c.cuyes} /> : <p>No aplica: sin inventario ni configuración de cuyes.</p>}
      <h3>Actividad del personal</h3>
      <p>Cuenta hechos registrados o asignados, no califica el desempeño individual.</p>
      {!c.activity.length && <p>Sin actividad en el período.</p>}
      {c.activity.map(a => <article className="card" key={a.id}><strong>{a.name}</strong>
        <p>Ordeños como responsable: {a.milkings} ({num(a.milk_liters)} L) · Recogidas de leche: {a.milk_pickups} · Recepciones de leche: {a.milk_receptions}</p>
        <p>Movimientos de cuyes registrados: {a.cuy_records} · Viajes de cuyes con salida: {a.cuy_pickups}</p>
      </article>)}
    </section>)}
  </section>
}

function MilkSection({ data }: { data: Milk }) {
  return <>
    <p><strong>{num(data.liters)} L producidos</strong> · {data.milkings} ordeños confirmados · {num(data.sent)} L recogidos · {num(data.received)} L recibidos</p>
    <p>Diferencia en recepciones con recogida registrada: {num(data.reception_difference)} L · Entregas pendientes hoy: {data.pending}</p>
    <Bars title="Litros producidos por mes" values={data.monthly} /><Bars title="Litros por turno" values={data.turns} />
    <details><summary>Producción por vaca ({data.cows.length})</summary><ul>{data.cows.map(c => <li key={c.code}>
      {c.code}{c.name && ` · ${c.name}`}: {c.liters === null ? 'Sin ordeño registrado' : `${num(c.liters)} L (${c.records} registros)`}
    </li>)}</ul></details>
    <details><summary>Trazabilidad de leche ({data.trace.length} envíos)</summary>{data.trace.map(t => <article className="card" key={t.code}>
      <strong>{t.destination} · {label(t.state)}</strong><p>Conductor: {t.driver} · Solicitud: {time(t.requested)}</p>
      <p>Recogida: {time(t.pickup)} · Recepción: {time(t.reception)}</p>
      <p>Programado: {num(t.planned)} L · Salida: {t.sent == null ? 'Pendiente' : `${num(t.sent)} L`} · Recibido: {t.received == null ? 'Pendiente' : `${num(t.received)} L`}</p>
      <ul>{t.lots.map((l, i) => <li key={i}>Ordeño {l.date} · lote {l.code} · {num(l.liters)} L programados</li>)}</ul>
    </article>)}</details>
  </>
}

function CuySection({ data }: { data: Cuyes }) {
  return <>
    <p><strong>{num(data.population)} cuyes al cierre del período</strong> · {data.births} nacidos vivos · {data.stillborn} natimortos · {data.deaths} muertes · {data.weaned} destetados</p>
    <p>Natalidad: {pct(data.birth_rate)} · Mortalidad: {pct(data.mortality_rate)} · Natimortalidad: {pct(data.stillborn_rate)}</p>
    <details><summary>Cómo se calculan las tasas</summary><p>Natalidad y mortalidad: nacidos vivos o muertes por cada 100 cuyes de población media diaria. Natimortalidad: natimortos por cada 100 nacidos totales.</p></details>
    <p>Traslados internos: {data.moved} · Despachos entre centros: {data.dispatched} · Recepciones: {data.received} · Reclasificados: {data.reclassified} · Ajuste neto: {data.adjusted} · Conteos pendientes: {data.pending_counts} · Alertas abiertas: {data.alerts}</p>
    <Bars title="Población al cierre de cada mes" values={Object.fromEntries(Object.entries(data.monthly).map(([key, m]) => [key, m.population]))} />
    <Bars title="Nacidos vivos por mes" values={Object.fromEntries(Object.entries(data.monthly).map(([key, m]) => [key, m.births]))} />
    <Bars title="Mortalidad por mes (animales)" values={Object.fromEntries(Object.entries(data.monthly).map(([key, m]) => [key, m.deaths]))} />
    <details><summary>Inventario por galpón y poza ({data.pens.length})</summary>
      {[...new Set(data.pens.map(p => p.shed))].map(s => <section key={s}><h4>{s} · {num(data.pens.filter(p => p.shed === s).reduce((total, p) => total + p.population, 0))} cuyes</h4>
        <ul>{data.pens.filter(p => p.shed === s).map(p => <li key={p.code}><strong>{p.code}</strong> · {p.purpose} · {p.population}/{p.capacity} · {p.composition.map(x => `${x.quantity} ${x.category}/${x.quality}`).join(', ')}</li>)}</ul>
      </section>)}</details>
    <p>Ventas: {data.sales.dispatched_units} cuyes despachados · {data.sales.delivered} pedidos entregados · {data.sales.pending} pendientes · {data.sales.expired} reservas vencidas</p>
    <p>Pagos originales validados: {Object.entries(data.sales.validated_payments).map(([currency, amount]) => `${currency} ${num(amount)}`).join(' · ') || 'Sin pagos en el período'}</p>
    <details><summary>Trazabilidad de ventas ({data.trace.length} órdenes)</summary>{data.trace.map(t => <article className="card" key={t.code}>
      <strong>{t.code} · {label(t.state)} · {t.point || label(t.mode)}</strong>
      <p>Solicitud: {time(t.registered_at)} · Salida: {time(t.dispatched_at)}</p>
      <ul>{t.origins.map((o, i) => <li key={i}>{o.shed} / {o.pen} · lote {o.lot} · {o.quantity} {o.category}/{o.quality}</li>)}</ul>
      <ul>{t.delivery.map(d => <li key={d.stage}>{label(d.stage)} · {time(d.time)} · Realizó: {d.performed_by} · Registró: {d.registered_by}</li>)}</ul>
    </article>)}</details>
  </>
}
