import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useLiveQuery } from 'dexie-react-hooks'
import { Link } from 'react-router-dom'
import { api, apiMode } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { useWorkspace } from '../auth/workspace'
import { Button, Notice } from '../components/ui'
import { db, listEvents } from '../offline/db'
import { useConnection } from '../offline/SyncPanel'
import { applyChanges } from '../offline/prepare'
import { allPages, makeCuyCommand, submitCuyCommand } from './actions'
import { ConfigPanel } from './ConfigPanel'
import { OperationForm } from './OperationForm'
import { limaToday, purposes, type Count, type CuyType, type Daily, type Dashboard, type Destination, type Ledger, type Pen, type Shed, type Transfer } from './types'

export function CuyesPage() {
  const { account } = useAuth()
  const { assignment } = useWorkspace()
  const online = useConnection()
  const cache = useQueryClient()
  const admin = assignment?.role === 'ADMIN'
  const [shedId, setShedId] = useState('')
  const [penId, setPenId] = useState('')
  const [month, setMonth] = useState(limaToday().slice(0, 7))
  const [boardScope, setBoardScope] = useState('')
  const [reason, setReason] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [redirect, setRedirect] = useState('')
  const copies = useLiveQuery(() => db.copies.where('account_id').equals(account?.id ?? '').toArray(), [account?.id])
  const events = useLiveQuery(() => listEvents(account?.id ?? ''), [account?.id])
  const query = useQuery({
    queryKey: ['cuyes', account?.id, assignment?.id, month, boardScope], enabled: !!account && online && apiMode === 'http',
    refetchInterval: 15000,
    queryFn: async () => {
      const start = `${month}-01`
      const last = new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)), 0).getDate()
      const end = `${month}-${String(last).padStart(2, '0')}` < limaToday() ? `${month}-${String(last).padStart(2, '0')}` : limaToday()
      const [pens, sheds, destinations, transfers, counts, daily, ledger, dashboard] = await Promise.all([
        allPages<Pen>('/cuyes/pens'), allPages<Shed>('/cuyes/sheds'), allPages<Destination>('/cuyes/destinations'),
        allPages<Transfer>('/cuyes/transfers'), allPages<Count>('/cuyes/counts'), allPages<Daily>('/cuyes/daily-reports'),
        allPages<Ledger>('/cuyes/kardex'), api.request<Dashboard>(`/cuyes/dashboard?start=${start}&end=${end}${boardScope ? `&${boardScope}` : ''}`),
      ])
      return { pens, sheds, destinations, transfers, counts, daily, ledger, dashboard }
    },
  })
  const pens = online ? query.data?.pens ?? [] : (copies ?? []).filter(c => c.kind === 'cuy_pen').map(c => c.document as Pen)
  const sheds = online ? query.data?.sheds ?? [] : (copies ?? []).filter(c => c.kind === 'cuy_shed').map(c => c.document as Shed)
  const scopeSheds = sheds.filter(s => admin || s.center_id === assignment?.location_id)
  const selectedShed = scopeSheds.find(s => s.id === shedId) ?? scopeSheds[0]
  const visiblePens = pens.filter(p => p.shed_id === selectedShed?.id)
  const pen = visiblePens.find(p => p.id === penId) ?? visiblePens[0]
  const refresh = () => {
    void cache.invalidateQueries({ queryKey: ['cuyes'] })
    if (account && navigator.onLine) void applyChanges(account.id).catch(() => { /* explicit preparation remains available */ })
  }
  async function action(type: CuyType, payload: Record<string, unknown>) {
    setBusy(true); setMessage('')
    try {
      if (!reason.trim()) throw new Error('Escribe el motivo administrativo o de confirmación.')
      const command = await makeCuyCommand(account!.id, type, { date: limaToday(), reason, ...payload })
      setMessage(await submitCuyCommand(account!.id, command)); refresh()
    } catch (e) { setMessage((e as Error).message) } finally { setBusy(false) }
  }
  if (apiMode === 'mock') return <Notice tone="warning">Cuyes requiere la API real. No se crean saldos simulados. Configura VITE_API_MODE=http.</Notice>
  return <section className="stack cuyes-module"><h1>Cuyes · Inventario por poza</h1>
    <p>Saldo confirmado del servidor. Las novedades pendientes de un teléfono no están incluidas.</p>
    <Link to="/sincronizacion">Preparar dispositivo / revisar sincronización</Link>
    {!online && <Notice tone="warning">Sin conexión: se muestra la última copia autorizada, no un saldo en tiempo real. Solo nacimientos y mortalidad pueden guardarse localmente.</Notice>}
    {query.isPending && online && <Notice>Cargando inventario…</Notice>}{query.isError && <Notice tone="error">{(query.error as Error).message}</Notice>}
    {admin && online && <ConfigPanel accountId={account!.id} pens={pens} sheds={sheds} onSaved={refresh} />}
    <div className="card stack form"><label>Galpón<select aria-label="Galpón" value={selectedShed?.id ?? ''} onChange={e => { setShedId(e.target.value); setPenId('') }}><option value="">Selecciona</option>{scopeSheds.map(s => <option key={s.id} value={s.id}>{s.name} · {s.code}</option>)}</select></label>
      <label>Poza<select aria-label="Poza" value={pen?.id ?? ''} onChange={e => setPenId(e.target.value)}><option value="">Selecciona</option>{visiblePens.map(p => <option key={p.id} value={p.id}>{p.code} · {p.population}/{p.capacity}</option>)}</select></label>
    </div>
    <div className="cuy-grid">{visiblePens.map(p => <button type="button" className="card" key={p.id} onClick={() => setPenId(p.id)} aria-pressed={pen?.id === p.id}><strong>{p.code}</strong><p>{purposes[p.purpose]}</p><p>{p.population} / {p.capacity} animales</p>{p.overcapacity && <strong>¡Sobrecapacidad!</strong>}</button>)}</div>
    {pen && <section className="card stack"><h2>{pen.code} · {pen.center}</h2><p>{purposes[pen.purpose]} · {pen.active ? 'Activa' : 'Inactiva'} · Machos {pen.totals.MACHO} · Hembras {pen.totals.HEMBRA} · Lactantes {pen.totals.LACTANTE}</p>
      <p>Último conteo: {pen.last_count ?? 'sin conteo'} · Último cierre: {pen.last_close ?? 'sin cierre'}</p>
      {pen.occupations.map(o => <details key={o.id} className="card"><summary>Lote {o.lot.id.slice(0, 8)} · {o.lot.provenance} {o.closed_on && '· ocupación cerrada'}</summary><p>Edad: {o.lot.age_days_min === null ? 'edad desconocida' : `${o.lot.age_days_min}–${o.lot.age_days_max} días`}</p><p>Apertura del lote: {o.lot.opened_on}{pen.purpose.startsWith('RECRIA') && ` · ${o.lot.rearing_days} días en recría`}</p><p>Antigüedad reproductiva: {o.lot.reproductive_days === null ? 'desconocida' : `${o.lot.reproductive_days} días`}</p>{o.lot.parent_id && <p>Lote de origen: {o.lot.parent_id} · Ocupación madre: {o.lot.source_occupation_id}</p>}{o.balances.map(b => <p key={`${b.category}:${b.quality}`}>{b.category} · {b.quality}: <strong>{b.quantity}</strong></p>)}</details>)}
    </section>}
    <OperationForm key={`${assignment?.id}:${pen?.id}`} accountId={account!.id} admin={admin} pen={pen} pens={pens} sheds={scopeSheds} destinations={query.data?.destinations ?? []} onSaved={refresh} />
    <section className="card stack"><h2>Novedades de este dispositivo</h2>{events?.filter(e => e.command.type.startsWith('CUY_')).map(e => <article key={e.event_id}><strong>{e.command.type} · {String(e.command.payload.date)} · {e.status === 'RECHAZADA' ? e.reviewed_at ? 'Rechazada · revisión reconocida, sin aplicar' : 'Requiere revisión' : e.status}</strong><p>{e.error?.message}</p><small>UUID {e.event_id}; la intención original se conserva.</small>{e.reviewed_at && <p>Revisión local: {e.review_reason} · {e.reviewed_at}</p>}{e.status === 'RECHAZADA' && !e.reviewed_at && <div className="stack"><p>Esto NO aplica el hecho rechazado ni cambia el saldo. Revisa el Kardex y, si corresponde, registra una nueva intención desde el formulario.</p><label>Motivo de reconocimiento de la revisión<input value={reason} onChange={event => setReason(event.target.value)} maxLength={500} /></label><Button disabled={!online || !reason.trim()} variant="secondary" onClick={() => void db.events.update(e.event_id, { reviewed_at: new Date().toISOString(), review_reason: reason.trim() })}>Reconocer revisión sin aplicar inventario</Button></div>}</article>)}</section>
    {online && query.data && <>
      <section className="card stack"><h2>Tablero confirmado</h2><label>Ámbito del tablero<select value={boardScope} onChange={e => setBoardScope(e.target.value)}><option value="">Todos mis ámbitos autorizados</option>{[...new Map(pens.map(p => [p.center_id, p.center])).entries()].map(([id, name]) => <option key={id} value={`center_id=${id}`}>Centro: {name}</option>)}{scopeSheds.map(s => <option key={s.id} value={`shed_id=${s.id}`}>Galpón: {s.name}</option>)}{pens.map(p => <option key={p.id} value={`pen_id=${p.id}`}>Poza: {p.code}</option>)}</select></label><label>Mes de indicadores<input type="month" max={limaToday().slice(0, 7)} value={month} onChange={e => setMonth(e.target.value)} /></label>
        <p>Población: {query.data.dashboard.population} · En tránsito: {query.data.dashboard.in_transit}</p><p>Actualizado: {new Date(query.data.dashboard.updated_at).toLocaleString('es-PE', { timeZone: 'America/Lima' })}</p>
        {query.data.dashboard.indicators.map(i => <article key={i.pen}><h3>{i.pen}</h3><p>Nacidos vivos {i.live} · Natimortos {i.stillborn} · Mortalidad {i.mortality} · Destetados {i.weaned}</p><p>Promedio de hembras: {i.average_females ?? 'datos insuficientes'} · Destetados/hembra: {i.weaned_per_female ?? 'datos insuficientes'}</p></article>)}
      </section>
      <section className="card stack"><h2>Acciones de revisión y confirmación</h2><label>Motivo para la acción<input value={reason} onChange={e => setReason(e.target.value)} maxLength={500} /></label>
        {message && <Notice>{message}</Notice>}
        {query.data.transfers.filter(t => t.state === 'EN_TRANSITO').map(t => <article className="card stack" key={t.id}><h3>{t.source} → {t.destination}</h3><p>{t.items.reduce((s, i) => s + i.quantity, 0)} animales en tránsito</p>
          {pens.some(p => p.id === t.destination_id) && <><Button disabled={busy} onClick={() => void action('CUY_RECEIVE', { transfer_id: t.id })}>Confirmar recepción física</Button><label>Redirigir destino<select value={redirect} onChange={e => setRedirect(e.target.value)}><option value="">Selecciona</option>{pens.filter(p => p.id !== t.destination_id && (admin || p.center_id === pens.find(p => p.id === t.destination_id)?.center_id)).map(p => <option key={p.id} value={p.id}>{p.code}</option>)}</select></label><Button disabled={busy || !redirect} onClick={() => void action('CUY_REDIRECT', { transfer_id: t.id, destination_id: redirect })}>Redirigir con motivo</Button></>}
        </article>)}
        {query.data.counts.filter(c => c.pen_id === pen?.id).map(c => <article className="card" key={c.id}><h3>{c.opening ? 'Apertura' : 'Conteo'} · {c.date} · {c.state}</h3>{c.details.map((d, i) => <p key={i}>{d.category}/{d.quality}: esperado {d.expected}, observado {d.observed}, diferencia {d.difference > 0 ? '+' : ''}{d.difference}</p>)}{admin && c.state === 'PENDIENTE' && <div className="row"><Button disabled={busy} onClick={() => void action('CUY_REVIEW', { count_id: c.id, approve: true })}>Aprobar ajuste</Button><Button disabled={busy} variant="secondary" onClick={() => void action('CUY_REVIEW', { count_id: c.id, approve: false })}>Rechazar diferencia</Button></div>}</article>)}
        {query.data.daily.filter(d => d.shed_id === selectedShed?.id).map(d => <article key={d.id}><p>Parte {d.date}: {d.state}</p>{d.revisions.map((r, i) => <small key={i}>{r.action} · {r.reason} · {r.registered_at}<br /></small>)}{admin && d.state === 'CERRADO' && <Button disabled={busy} variant="secondary" onClick={() => void action('CUY_REOPEN', { shed_id: d.shed_id, date: d.date })}>Reabrir con motivo</Button>}</article>)}
        {query.data.dashboard.alerts.map(a => <article key={a.id}><Notice tone="warning">{a.text}</Notice>{admin && <Button disabled={busy} onClick={() => void action('CUY_RESOLVE', { alert_id: a.id })}>Resolver alerta con motivo</Button>}</article>)}
        {admin && <Button disabled={busy} onClick={() => void action('CUY_ALERTS', {})}>Evaluar alertas de antigüedad y rendimiento</Button>}
      </section>
      <section className="card stack"><h2>Kardex de {pen?.code ?? 'poza'}</h2>{query.data.ledger.filter(m => m.lines.some(l => l.snapshot.pen_id === pen?.id) || pen?.occupations.some(o => o.id === m.metadata?.occupation_id)).map(m => <article className="card" key={m.id}><h3>{m.kind} · {m.date}</h3><p>{m.actor} · {m.reason} · Registrado {m.registered_at}</p>{m.kind === 'BIRTH' && <p>Nacidos vivos {String(m.metadata.live)} · Natimortos {String(m.metadata.stillborn)}</p>}{m.lines.map((l, i) => <p key={i}>{l.snapshot.center}/{l.snapshot.shed}/{l.snapshot.pen} · lote {l.snapshot.lot_id.slice(0, 8)} · {l.category}/{l.quality}: {l.delta > 0 ? '+' : ''}{l.delta}</p>)}{admin && ['BIRTH', 'DEATH', 'WEAN', 'MOVE', 'RECLASS'].includes(m.kind) && <Button disabled={busy} variant="secondary" onClick={() => void action('CUY_COMPENSATE', { movement_id: m.id })}>Registrar compensación con motivo</Button>}</article>)}</section>
    </>}
  </section>
}
