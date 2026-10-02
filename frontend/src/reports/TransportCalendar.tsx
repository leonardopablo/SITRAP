import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, apiMode } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { useConnection } from '../offline/SyncPanel'
import { Button, Notice } from '../components/ui'
import { monthLabel, monthRange, sumMetric, type TransferMetrics } from './calendar'

export function TransportCalendar() {
  const { account } = useAuth()
  const online = useConnection()
  const now = new Date()
  const [current, setCurrent] = useState({ year: now.getFullYear(), month: now.getMonth() })
  const [selected, setSelected] = useState<string | null>(null)
  const range = monthRange(current.year, current.month)
  const query = useQuery({ queryKey: ['transport-calendar', account?.id, range.from, range.to], queryFn: () => api.request<TransferMetrics>(`/metrics/transfers?from=${range.from}&to=${range.to}`), enabled: !!account && online })
  const days = query.data?.days ?? []
  function move(offset: number) { const date = new Date(Date.UTC(current.year, current.month + offset, 1)); setCurrent({ year: date.getUTCFullYear(), month: date.getUTCMonth() }); setSelected(null) }
  return <section className="stack"><h1>Diario de transporte</h1>
    {apiMode === 'mock' && <Notice tone="warning">Calendario de datos de demostración. No representa viajes confirmados en el servidor.</Notice>}
    <p>Litros recogidos y litros recibidos en destino son medidas distintas; no deben sumarse como producción.</p>
    <div className="row"><Button variant="secondary" onClick={() => move(-1)} aria-label="Mes anterior">‹</Button><h2>{monthLabel(current.year, current.month)}</h2><Button variant="secondary" onClick={() => move(1)} aria-label="Mes siguiente">›</Button></div>
    {query.isPending && <Notice>Cargando período…</Notice>}
    {query.isError && <Notice tone="error">No se pudieron consultar los viajes. <Button variant="secondary" onClick={() => void query.refetch()}>Reintentar</Button></Notice>}
    {query.data && <><p>Corte: {new Intl.DateTimeFormat('es-PE', { dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Lima' }).format(new Date(query.data.cutoff_at))} · {query.data.time_zone}</p>
      <div className="row"><span className="card">Recogido: <strong>{sumMetric(days, 'picked_litres')} L</strong></span><span className="card">Recibido: <strong>{sumMetric(days, 'received_litres')} L</strong></span></div>
      <div className="calendar" role="group" aria-label="Días del mes">{Array.from({ length: range.days }, (_, index) => {
        const date = `${range.from.slice(0, 8)}${String(index + 1).padStart(2, '0')}`
        const metric = days.find(day => day.date === date)
        return <button type="button" key={date} className="calendar-day" aria-pressed={selected === date} onClick={() => setSelected(date)}><strong>{index + 1}</strong><span>{metric?.picked_litres ?? '0'} L recogidos</span><span>{metric?.received_litres ?? '0'} L recibidos</span></button>
      })}</div>
      <h2>Listado por día</h2><ul>{days.map(day => <li key={day.date}><button className="button secondary" onClick={() => setSelected(day.date)}>{day.date}: {day.picked_litres} L recogidos; {day.received_litres} L recibidos</button></li>)}</ul>
      {selected && <section className="card"><h3>Viajes del {selected}</h3>{(days.find(day => day.date === selected)?.transfers ?? []).length ? days.find(day => day.date === selected)?.transfers.map(item => <p key={item.id}><Link to={`/entregas/${item.id}`}>{item.code}</Link> · {item.picked_litres} L recogidos · {item.received_litres} L recibidos · {item.state}</p>) : <p>No hay viajes documentados en esta fecha.</p>}</section>}
    </>}
  </section>
}
