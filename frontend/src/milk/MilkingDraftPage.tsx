import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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
import { draftDetails, formatLitres, parseLitres } from './draft'

interface Draft { id: string; version_id: string; center_id: string; date: string; shift_id: string; values: Record<string, string>; last_event_id: string; next_version: number }
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
  const [animals, setAnimals] = useState<Animal[]>([])
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
    <div className="row"><Button busy={saving} disabled={!ready || !animals.length || !!invalid} onClick={() => void save()}>Guardar borrador</Button><Button variant="secondary" onClick={() => navigate('/sincronizacion')}>Ver pendientes</Button></div>
    {draft && <Notice tone="warning">Borrador guardado en este teléfono. Pendiente de enviar. Evento {draft.last_event_id}. No confirmado en el sistema.</Notice>}
  </section>
}
