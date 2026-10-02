import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, apiMode } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { useWorkspace } from '../auth/workspace'
import { useConnection } from '../offline/SyncPanel'
import { Button, Notice } from '../components/ui'
import { cowTotals, type MilkMetrics } from './milk'

const today = () => { const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date()); const get = (type: string) => parts.find(part => part.type === type)?.value; return `${get('year')}-${get('month')}-${get('day')}` }
export function MilkAnalytics() {
  const { account } = useAuth()
  const { assignment } = useWorkspace()
  const online = useConnection()
  const [from, setFrom] = useState(`${today().slice(0, 7)}-01`)
  const [to, setTo] = useState(today())
  const [period, setPeriod] = useState({ from, to })
  const valid = /^\d{4}-\d{2}-\d{2}$/.test(from) && /^\d{4}-\d{2}-\d{2}$/.test(to) && from <= to
  const query = useQuery({ queryKey: ['milk-metrics', account?.id, assignment?.id, period.from, period.to], queryFn: () => api.request<MilkMetrics>(`/metrics/milk?from=${period.from}&to=${period.to}&center_id=${encodeURIComponent(assignment?.location_id ?? '')}`), enabled: !!account && !!assignment && online })
  const cows = cowTotals(query.data?.points ?? [])
  return <section className="stack"><h1>Análisis de producción</h1>
    {apiMode === 'mock' && <Notice tone="warning">Gráfico de demostración. No representa mediciones reales del centro.</Notice>}
    <div className="row"><div className="field"><label htmlFor="milk-from">Desde</label><input id="milk-from" type="date" value={from} onChange={event => setFrom(event.target.value)} /></div><div className="field"><label htmlFor="milk-to">Hasta</label><input id="milk-to" type="date" value={to} onChange={event => setTo(event.target.value)} /></div><Button disabled={!valid} onClick={() => setPeriod({ from, to })}>Consultar</Button></div>
    {!valid && <Notice tone="error">Elige un período válido.</Notice>}
    {query.isPending && online && <Notice>Cargando producción…</Notice>}
    {query.isError && <Notice tone="error">No se pudo consultar el análisis. <Button variant="secondary" onClick={() => void query.refetch()}>Reintentar</Button></Notice>}
    {!online && <Notice tone="warning">Necesitas conexión para consultar métricas actualizadas.</Notice>}
    {query.data && <><p>Período {period.from} a {period.to} · Corte {new Intl.DateTimeFormat('es-PE', { dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Lima' }).format(new Date(query.data.cutoff_at))}</p>
      <div className="row"><div className="card">Total vigente: <strong>{query.data.total_litres} L</strong></div><div className="card">Promedio por día registrado: <strong>{query.data.average_per_registered_day} L</strong></div><div className="card">Días con registro: <strong>{query.data.days_registered} / {query.data.expected_days}</strong></div></div>
      <p>Ausencia de dato no es cero. Estos litros no miden rentabilidad ni justifican decisiones veterinarias.</p>
      {cows.length > 0 && <div className="card" aria-label="Gráfico de litros por vaca"><ResponsiveContainer width="100%" height={260}><BarChart data={cows}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="code" /><YAxis unit=" L" /><Tooltip formatter={(value) => `${value} L`} /><Bar dataKey="litres" fill="#237a57" name="Litros" /></BarChart></ResponsiveContainer></div>}
      <h2>Detalle por vaca</h2><ul>{cows.map(cow => <li key={cow.code}>{cow.code}: {cow.litres.toLocaleString('es-PE', { maximumFractionDigits: 3 })} L · {cow.registered} registros</li>)}</ul>
      {cows.length === 0 && <p>No hay producción registrada en este período.</p>}
    </>}
  </section>
}
