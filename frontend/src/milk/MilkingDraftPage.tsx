import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, apiMode } from '../api/client'
import type { Page } from '../api/types'
import type { Animal } from '../animals/types'
import { useAuth } from '../auth/AuthProvider'
import { useWorkspace } from '../auth/workspace'
import { createCommand } from '../api/commands'
import { db, enqueue, getDevice, readCopy, saveCopy } from '../offline/db'
import { useConnection } from '../offline/SyncPanel'
import { Button, Field, Notice } from '../components/ui'
import { confirmable, draftDetails, formatLitres, parseLitres } from './draft'
import { useLiveQuery } from 'dexie-react-hooks'

interface Draft { id: string; version_id: string; center_id: string; date: string; shift_id: string; values: Record<string, string>; last_event_id: string; next_version: number; confirm_event_id?: string; lot_id?: string }
const todayLima = () => { const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date()); const get = (key: string) => parts.find(part => part.type === key)?.value ?? ''; return `${get('year')}-${get('month')}-${get('day')}` }
export function MilkingDraftPage() {
  const { account } = useAuth()
  const { assignment } = useWorkspace()
  const online = useConnection()
  const navigate = useNavigate()
  const [date, setDate] = useState(todayLima())
  const [shift, setShift] = useState('diario-demo')
  const [values, setValues] = useState<Record<string, string>>({})
  const [draft, setDraft] = useState<Draft | null>(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [ready, setReady] = useState(false)
  const [review, setReview] = useState(false)
  const [animals, setAnimals] = useState<Animal[]>([])
  const confirmation = useLiveQuery(() => draft?.confirm_event_id ? db.events.get(draft.confirm_event_id) : undefined, [draft?.confirm_event_id])
  const source = useQuery({ queryKey: ['milking-animals', account?.id, assignment?.id], queryFn: () => api.request<Page<Animal>>('/animals'), enabled: !!account && !!assignment && online })
  useEffect(() => {
    if (!account || !assignment) return
    let active = true
    void (async () => {
      const entry = await readCopy(account.id, 'milking-draft', assignment.location_id ?? '')
      if (entry?.document && active) {
        const copy = entry.document as Draft
        setDraft(copy); setDate(copy.date); setShift(copy.shift_id); setValues(copy.values)
      }
      if (!navigator.onLine) {
        const copies = await db.copies.where('[account_id+kind]').equals([account.id, 'animal']).toArray()
        if (active) setAnimals(copies.map(item => item.document as Animal).filter(item => item.center_id === assignment.location_id && item.status === 'ACTIVO'))
      }
      if (active) setReady(true)
    })().catch(() => { if (active) { setError('No se pudieron abrir los datos locales.'); setReady(true) } })
    return () => { active = false }
  }, [account?.id, assignment?.id])
  useEffect(() => {
    if (!source.data || !account || !assignment) return
    const active = source.data.results.filter(item => item.status === 'ACTIVO' && item.center_id === assignment.location_id)
    setAnimals(active)
    void Promise.all(active.map(item => saveCopy(account.id, 'animal', item.id, item))).catch(() => setError('No se pudieron preparar vacas para consulta local.'))
  }, [source.data, account?.id, assignment?.id])
  let total = 0; let invalid = ''
  for (const animal of animals) { try { total += parseLitres(values[animal.id] ?? '') ?? 0 } catch (cause) { invalid = `${animal.code}: ${(cause as Error).message}` } }
  async function save() {
    if (!account || !assignment?.location_id || saving) return
    setError('')
    if (invalid) { setError(invalid); return }
    if (!animals.length) { setError('Necesitas vacas descargadas para guardar el ordeño.'); return }
    if (draft?.confirm_event_id) { setError('La confirmación ya está guardada. Comprueba su estado en Pendientes.'); return }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !shift) { setError('Revisa fecha y turno.'); return }
    setSaving(true)
    try {
      const device = await getDevice(account.id)
      if (draft) {
        const previous = await db.events.get(draft.last_event_id)
        if (previous?.status === 'RECHAZADA') throw new Error('El borrador anterior fue rechazado. Revísalo antes de registrar otra intención.')
      }
      const next: Draft = draft ? { ...draft, date, shift_id: shift, values: structuredClone(values), next_version: draft.next_version + 1 } : { id: crypto.randomUUID(), version_id: crypto.randomUUID(), center_id: assignment.location_id, date, shift_id: shift, values: structuredClone(values), last_event_id: '', next_version: 1 }
      const command = createCommand({ type: draft ? 'MILKING_UPDATE' : 'MILKING_CREATE', entity_id: next.id, device_id: device.device_id, ...(draft ? { expected_version: draft.next_version, depends_on: [draft.last_event_id] } : {}), payload: { center_id: next.center_id, date, shift_id: shift, version_id: next.version_id, details: draftDetails(animals, values) } })
      await enqueue(account.id, command)
      next.last_event_id = command.event_id
      await saveCopy(account.id, 'milking-draft', assignment.location_id, next)
      setDraft(next)
      setReview(false)
    } catch (cause) { setError((cause as Error).message) }
    finally { setSaving(false) }
  }
  const unchanged = !!draft && draft.date === date && draft.shift_id === shift && JSON.stringify(draft.values) === JSON.stringify(values)
  async function confirm() {
    if (!account || !assignment?.location_id || !draft || draft.confirm_event_id || saving) return
    setError('')
    if (!unchanged) { setError('Guarda los cambios antes de confirmar.'); return }
    if (!confirmable(animals, draft.values)) { setError('Registra los litros de todas las vacas y un total mayor que 0 L. Cero explícito sí está permitido.'); return }
    setSaving(true)
    try {
      const parent = await db.events.get(draft.last_event_id)
      if (!parent || parent.status === 'RECHAZADA') throw new Error('El borrador no es confirmable; revisa el registro anterior.')
      const device = await getDevice(account.id)
      const lotId = crypto.randomUUID()
      const command = createCommand({ type: 'MILKING_CONFIRM', entity_id: draft.id, device_id: device.device_id, expected_version: draft.next_version, depends_on: [draft.last_event_id], payload: { version_id: draft.version_id, lot_id: lotId } })
      await enqueue(account.id, command)
      const updated = { ...draft, confirm_event_id: command.event_id, lot_id: lotId }
      await saveCopy(account.id, 'milking-draft', assignment.location_id, updated)
      setDraft(updated); setReview(false)
    } catch (cause) { setError((cause as Error).message) }
    finally { setSaving(false) }
  }
  return <section className="stack form"><h1>Registrar producción por vaca</h1>
    {apiMode === 'mock' && <Notice tone="warning">Modo simulado: este registro puede guardarse solo en este teléfono; nadie más lo verá. No existe lote ni aviso remoto.</Notice>}
    {!ready && <Notice>Cargando borrador local…</Notice>}
    <div className="field"><label htmlFor="milking-date">Fecha de ordeño</label><input id="milking-date" type="date" value={date} onChange={event => setDate(event.target.value)} /></div>
    <div className="field"><label htmlFor="milking-shift">Turno</label><select id="milking-shift" value={shift} onChange={event => setShift(event.target.value)}><option value="diario-demo">Diario (turno demo; validar catálogo)</option></select></div>
    <p className="help">Centro: {assignment?.location_name}. Vacío significa sin dato; 0 L significa cero explícito.</p>
    {animals.length === 0 && <Notice tone="warning">No hay vacas activas descargadas. Consulta Vacas con conexión y prepara el dispositivo.</Notice>}
    {animals.map(animal => <Field key={animal.id} label={`${animal.code}${animal.name ? ` · ${animal.name}` : ''} (L)`} inputMode="decimal" value={values[animal.id] ?? ''} onChange={event => setValues(previous => ({ ...previous, [animal.id]: event.target.value }))} />)}
    <p className="quantity">Total: {formatLitres(total)}</p>
    {invalid && <Notice tone="error">{invalid}</Notice>}
    {error && <Notice tone="error">{error}</Notice>}
    <div className="row"><Button busy={saving} disabled={!ready || !animals.length || !!invalid || !!draft?.confirm_event_id} onClick={() => void save()}>Guardar borrador</Button><Button variant="secondary" disabled={!draft || !!draft.confirm_event_id || !unchanged} onClick={() => setReview(true)}>Revisar producción</Button><Button variant="secondary" onClick={() => navigate('/sincronizacion')}>Ver pendientes</Button></div>
    {review && draft && !draft.confirm_event_id && <section className="card stack"><h2>Revisar antes de confirmar</h2><p>Fecha: {draft.date} · Turno: {draft.shift_id} · Centro: {assignment?.location_name}</p>
      <ul>{animals.map(animal => <li key={animal.id}>{animal.code}: {draft.values[animal.id] === '' || draft.values[animal.id] === undefined ? 'Sin dato' : formatLitres(parseLitres(draft.values[animal.id]) ?? 0)}</li>)}</ul>
      <p className="quantity">Total: {formatLitres(total)}</p>
      {!confirmable(animals, draft.values) && <Notice tone="warning">Completa cada vaca; el total debe ser mayor que 0 L.</Notice>}
      <div className="row"><Button busy={saving} disabled={!confirmable(animals, draft.values)} onClick={() => void confirm()}>Confirmar producción</Button><Button variant="secondary" onClick={() => setReview(false)}>Volver a editar</Button></div>
    </section>}
    {draft && !draft.confirm_event_id && <Notice tone="warning">Borrador guardado en este teléfono. Pendiente de enviar. Evento {draft.last_event_id}. No confirmado en el sistema.</Notice>}
    {draft?.confirm_event_id && confirmation?.status !== 'APLICADA' && <Notice tone="warning">Confirmación guardada solo en este teléfono. Evento {draft.confirm_event_id}. El lote {draft.lot_id} todavía no existe en el servidor; no puedes enviar una entrega a otra persona hasta recibir acuse.</Notice>}
    {confirmation?.status === 'APLICADA' && <Notice tone="success">Producción confirmada por el servidor. Lote {draft?.lot_id}. <Link to="/entregas/preparar">Preparar entrega</Link></Notice>}
  </section>
}
