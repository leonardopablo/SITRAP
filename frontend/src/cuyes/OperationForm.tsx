import { useRef, useState } from 'react'
import type { Command } from '../api/types'
import { Button, Notice } from '../components/ui'
import { BucketEditor, blankBucket } from './BucketEditor'
import { ensureDaySynced, makeCuyCommand, submitCuyCommand } from './actions'
import { categoriesForPurpose, limaToday, type Bucket, type CuyType, type Destination, type Pen, type Shed } from './types'

const operations: Partial<Record<CuyType, string>> = {
  CUY_OPEN: 'Apertura por conteo físico', CUY_BIRTH: 'Nacimiento', CUY_DEATH: 'Mortalidad',
  CUY_WEAN: 'Destete y sexaje', CUY_MOVE: 'Traslado inmediato', CUY_DISPATCH: 'Despacho a otro centro',
  CUY_RECLASS: 'Reclasificar calidad', CUY_COUNT: 'Conteo mensual', CUY_CLOSE: 'Cerrar parte diario',
}
export function OperationForm({ accountId, admin, pen, pens, sheds, destinations, onSaved }: {
  accountId: string; admin: boolean; pen: Pen | undefined; pens: Pen[]; sheds: Shed[]; destinations: Destination[]; onSaved: () => void
}) {
  const [kind, setKind] = useState<CuyType>('CUY_BIRTH')
  const [day, setDay] = useState(limaToday())
  const [reason, setReason] = useState('')
  const [occId, setOccId] = useState('')
  const [shedId, setShedId] = useState('')
  const [live, setLive] = useState(0)
  const [stillborn, setStillborn] = useState(0)
  const [quality, setQuality] = useState('SIN_CLASIFICAR')
  const [newQuality, setNewQuality] = useState('B')
  const [destination, setDestination] = useState('')
  const [items, setItems] = useState<Bucket[]>([{ ...blankBucket(), category: categoriesForPurpose(pen?.purpose)[0] }])
  const [outputs, setOutputs] = useState<Bucket[]>([{ ...blankBucket(), quality: 'B' }])
  const [provenance, setProvenance] = useState('')
  const [bornFrom, setBornFrom] = useState('')
  const [bornUntil, setBornUntil] = useState('')
  const [installed, setInstalled] = useState('')
  const [openingGroups, setOpeningGroups] = useState<{ lot: Record<string, string>; items: Bucket[] }[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const pending = useRef<{ fingerprint: string; command: Command } | null>(null)
  const offlineAllowed = kind === 'CUY_BIRTH' || kind === 'CUY_DEATH'
  const filteredDestinations = kind === 'CUY_DISPATCH' ? destinations.filter(d => d.center_id !== pen?.center_id) : pens.filter(p => p.id !== pen?.id && p.center_id === pen?.center_id && p.active && sheds.some(s => s.id === p.shed_id && s.active))
  async function submit() {
    setBusy(true); setMessage('')
    try {
      let payload: Record<string, unknown> = { date: day, reason }
      if (kind !== 'CUY_CLOSE' && !pen) throw new Error('Selecciona una poza.')
      if (kind === 'CUY_OPEN') {
        const group = { lot: { provenance, ...(bornFrom ? { born_from: bornFrom } : {}), ...(bornUntil ? { born_until: bornUntil } : {}), ...(installed ? { installed_on: installed } : {}) }, items }
        payload = { ...payload, pen_id: pen!.id, groups: [...openingGroups, group] }
      }
      if (kind === 'CUY_BIRTH') payload = { ...payload, occupation_id: occId, live, stillborn }
      if (kind === 'CUY_DEATH') payload = { ...payload, items, cause: reason || 'desconocida' }
      if (kind === 'CUY_WEAN') payload = { ...payload, occupation_id: occId, quality, quantity: outputs.reduce((s, i) => s + i.quantity, 0), destinations: outputs }
      if (kind === 'CUY_MOVE' || kind === 'CUY_DISPATCH') payload = { ...payload, source_id: pen!.id, destination_id: destination, items }
      if (kind === 'CUY_RECLASS') payload = { ...payload, items, new_quality: newQuality }
      if (kind === 'CUY_COUNT') payload = { ...payload, pen_id: pen!.id, items }
      if (kind === 'CUY_CLOSE') {
        const id = shedId || pen?.shed_id
        if (!id) throw new Error('Selecciona un galpón.')
        await ensureDaySynced(accountId, id, day, pens)
        payload = { ...payload, shed_id: id }
      }
      const fingerprint = JSON.stringify({ kind, payload })
      if (pending.current && pending.current.fingerprint !== fingerprint) throw new Error('Hay una intención sin acuse. Reintenta sin modificarla o descártala explícitamente antes de preparar otra.')
      const command = pending.current?.command ?? await makeCuyCommand(accountId, kind, payload)
      pending.current = { fingerprint, command }
      const result = await submitCuyCommand(accountId, command)
      pending.current = null
      setMessage(result); onSaved()
    } catch (error) { setMessage((error as Error).message) }
    finally { setBusy(false) }
  }
  return <section className="card stack"><h2>Registrar novedad</h2>
    <label>Operación<select aria-label="Operación" value={kind} onChange={e => { setKind(e.target.value as CuyType); setItems([{ ...blankBucket(), category: categoriesForPurpose(pen?.purpose)[0] }]); setOccId(''); setMessage('') }}>{Object.entries(operations).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
    <Notice>{offlineAllowed ? 'Se guarda en la cola de este teléfono. Solo modifica el saldo confirmado cuando el servidor la acepta. Prepara el dispositivo en Sincronización.' : 'Requiere conexión y validación del servidor.'}</Notice>
    <form className="stack form" onSubmit={e => { e.preventDefault(); void submit() }}>
      <label>Fecha operativa (Perú)<input required type="date" max={limaToday()} value={day} onChange={e => setDay(e.target.value)} /></label>
      {kind === 'CUY_CLOSE' ? <label>Galpón<select required value={shedId || pen?.shed_id || ''} onChange={e => setShedId(e.target.value)}><option value="">Selecciona</option>{sheds.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label> : <p>Poza: <strong>{pen?.code ?? 'Selecciona una poza arriba'}</strong></p>}
      {(kind === 'CUY_BIRTH' || kind === 'CUY_WEAN') && <label>Lote de maternidad<select aria-label="Lote de maternidad" required value={occId} onChange={e => setOccId(e.target.value)}><option value="">Selecciona</option>{pen?.occupations.filter(o => !o.closed_on && o.balances.some(b => b.quantity > 0 && b.category === (kind === 'CUY_BIRTH' ? 'HEMBRA' : 'LACTANTE'))).map(o => <option key={o.id} value={o.id}>{o.lot.provenance} · {o.lot.id.slice(0, 8)}</option>)}</select></label>}
      {kind === 'CUY_BIRTH' && <><label>Nacidos vivos<input type="number" required min="0" step="1" value={live} onChange={e => setLive(Number(e.target.value))} /></label><label>Natimortos (no suman inventario)<input type="number" required min="0" step="1" value={stillborn} onChange={e => setStillborn(Number(e.target.value))} /></label></>}
      {kind === 'CUY_OPEN' && <><label>Procedencia del grupo<input required value={provenance} onChange={e => setProvenance(e.target.value)} /></label><label>Nacimiento desde (opcional)<input type="date" max={day} value={bornFrom} onChange={e => setBornFrom(e.target.value)} /></label><label>Nacimiento hasta (opcional)<input type="date" max={day} value={bornUntil} onChange={e => setBornUntil(e.target.value)} /></label><label>Instalación reproductiva (opcional)<input type="date" max={day} value={installed} onChange={e => setInstalled(e.target.value)} /></label></>}
      {['CUY_OPEN', 'CUY_DEATH', 'CUY_MOVE', 'CUY_DISPATCH', 'CUY_RECLASS', 'CUY_COUNT'].includes(kind) && <BucketEditor value={items} onChange={setItems} categories={categoriesForPurpose(pen?.purpose)} occupations={kind === 'CUY_OPEN' ? undefined : pen?.occupations} count={kind === 'CUY_OPEN' || kind === 'CUY_COUNT'} />}
      {kind === 'CUY_OPEN' && <><p>Si hay grupos de distinta procedencia o edad, sepáralos antes de enviar. Todos se abren juntos, sin mezclar su identidad.</p>{openingGroups.map((g, i) => <p key={i}>Grupo preparado: {g.lot.provenance} · {g.items.reduce((s, b) => s + b.quantity, 0)} animales <button type="button" onClick={() => setOpeningGroups(openingGroups.filter((_, index) => index !== i))}>Quitar grupo</button></p>)}<Button type="button" variant="secondary" disabled={!provenance || items.some(i => i.quantity < 0)} onClick={() => { setOpeningGroups([...openingGroups, { lot: { provenance, ...(bornFrom ? { born_from: bornFrom } : {}), ...(bornUntil ? { born_until: bornUntil } : {}), ...(installed ? { installed_on: installed } : {}) }, items: structuredClone(items) }]); setProvenance(''); setBornFrom(''); setBornUntil(''); setInstalled(''); setItems([blankBucket()]) }}>Preparar este grupo y añadir otro</Button></>}
      {(kind === 'CUY_MOVE' || kind === 'CUY_DISPATCH') && <label>Destino<select required value={destination} onChange={e => setDestination(e.target.value)}><option value="">Selecciona</option>{filteredDestinations.filter(d => d.id !== pen?.id && items.every(i => d.purpose === 'ENFERMERIA' || d.purpose === 'MATERNIDAD' || (d.purpose === 'ACABADO' && i.category !== 'LACTANTE') || d.purpose === (i.category === 'MACHO' ? 'RECRIA_MACHOS' : i.category === 'HEMBRA' ? 'RECRIA_HEMBRAS' : ''))).map(d => <option key={d.id} value={d.id}>{d.code}</option>)}</select></label>}
      {kind === 'CUY_WEAN' && <><label>Calidad de lactantes de origen<select value={quality} onChange={e => setQuality(e.target.value)}>{['SIN_CLASIFICAR', 'A', 'B', 'C'].map(q => <option key={q}>{q}</option>)}</select></label><BucketEditor value={outputs} onChange={setOutputs} destinations={filteredDestinations} weaning /></>}
      {kind === 'CUY_RECLASS' && <label>Nueva calidad<select value={newQuality} onChange={e => setNewQuality(e.target.value)}>{['SIN_CLASIFICAR', 'A', 'B', ...(admin ? ['C'] : [])].map(q => <option key={q}>{q}</option>)}</select></label>}
      {kind === 'CUY_COUNT' && <Notice tone="warning">Cuenta cada lote, categoría y calidad. Las combinaciones omitidas se registran como cero observado. Guardar no cambia existencias.</Notice>}
      <label>Motivo / causa probable<input required maxLength={500} value={reason} onChange={e => setReason(e.target.value)} placeholder={kind === 'CUY_DEATH' ? 'desconocida, si no se conoce la causa' : 'Describe el hecho registrado'} /></label>
      <Button type="submit" busy={busy} disabled={!offlineAllowed && !navigator.onLine}>Guardar {kind === 'CUY_CLOSE' ? 'cierre definitivo' : 'novedad'}</Button>
      {pending.current && !busy && <Button type="button" variant="secondary" onClick={() => { pending.current = null; setMessage('Intención liberada del formulario. Antes de volver a registrar, revisa el Kardex y la cola: la llamada anterior pudo haber sido aceptada.') }}>Liberar formulario para otra intención</Button>}
    </form>{message && <Notice>{message}</Notice>}
  </section>
}
