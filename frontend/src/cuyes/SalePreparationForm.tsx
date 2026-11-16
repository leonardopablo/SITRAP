import { useState } from 'react'
import { Button, Notice } from '../components/ui'
import { suggestFifo } from './salesActions'
import type { Candidate, Sale, SaleType, Selection } from './salesTypes'

export function SalePreparationForm({ order, candidates, shedIds, perform }: {
  order: Sale; candidates: Candidate[]; shedIds: string[];
  perform: (type: SaleType, payload: Record<string, unknown>) => Promise<boolean>
}) {
  const [items, setItems] = useState<Selection[]>(order.preparation?.items ?? [])
  const [reason, setReason] = useState('')
  const [message, setMessage] = useState('')
  const blank = (): Selection => ({ line_id: '', occupation_id: '', category: 'MACHO', quality: 'A', quantity: 1 })
  return <section className="card stack"><h3>Selección real de pozas</h3><p>FIFO es una sugerencia: primero lotes más antiguos, con desempate estable. Se conserva tu selección real. No se descuenta todavía.</p>
    <Button disabled={!candidates.length || !shedIds.length} variant="secondary" onClick={() => { try { setItems(suggestFifo(order, candidates)); setMessage('Sugerencia preparada; revisa cantidades y procedencias antes de guardar.') } catch (e) { setMessage((e as Error).message) } }}>Sugerir FIFO</Button>
    <form className="stack form" onSubmit={e => { e.preventDefault(); void perform('SALE_SELECT', { shed_ids: shedIds, items: items.map(({ line_id, occupation_id, category, quality, quantity }) => ({ line_id, occupation_id, category, quality, quantity })), reason }) }}>
      {items.map((item, index) => <fieldset className="card stack" key={index}><legend>Selección {index + 1}</legend>
        <label>Línea de la orden<select required aria-label="Línea de la orden" value={item.line_id} onChange={e => setItems(items.map((v, i) => i === index ? { ...v, line_id: e.target.value } : v))}><option value="">Selecciona ítem</option>{order.lines.map((line, i) => <option key={line.id} value={line.id}>Ítem {i + 1}: {line.kind} · {line.animal_count} animales</option>)}</select></label>
        <label>Ocupación de origen<select required aria-label="Ocupación de origen" value={`${item.occupation_id}:${item.category}:${item.quality}`} onChange={e => { const c = candidates.find(c => `${c.occupation_id}:${c.category}:${c.quality}` === e.target.value); if (c) setItems(items.map((v, i) => i === index ? { ...v, occupation_id: c.occupation_id, category: c.category, quality: c.quality, shed_id: c.shed_id } : v)) }}><option value="">Selecciona poza y lote</option>{candidates.filter(c => !item.line_id || order.lines.find(l => l.id === item.line_id)?.recipe.some(r => r.category === c.category && r.quality === c.quality)).map(c => <option key={`${c.occupation_id}:${c.category}:${c.quality}`} value={`${c.occupation_id}:${c.category}:${c.quality}`}>{c.pen} · lote {c.lot_id.slice(0, 8)} · apertura {c.opened_on} · {c.category}/{c.quality} · elegibles {c.available}</option>)}</select></label>
        <label>Cantidad efectiva prevista<input required type="number" min="1" step="1" value={item.quantity} onChange={e => setItems(items.map((v, i) => i === index ? { ...v, quantity: Number(e.target.value) } : v))} /></label><Button type="button" variant="secondary" onClick={() => setItems(items.filter((_, i) => i !== index))}>Quitar selección</Button>
      </fieldset>)}
      <Button type="button" variant="secondary" onClick={() => setItems([...items, blank()])}>Añadir selección</Button>
      <label>Motivo de preparación<input required maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <Notice tone="warning">Reemplaza la selección de tus galpones de este centro; conserva los otros orígenes e invalida las conformidades anteriores. Cada galpón debe confirmar el detalle nuevo.</Notice>
      <Button type="submit" disabled={!items.length || !shedIds.length || !reason.trim()}>Guardar selección sin retirar inventario</Button>
      {!!order.preparation?.items.length && <Button type="button" disabled={!reason.trim() || !shedIds.length} variant="secondary" onClick={() => void perform('SALE_SELECT', { shed_ids: shedIds, items: [], reason })}>Liberar explícitamente mi selección (la reserva comercial permanece)</Button>}
    </form>{message && <Notice>{message}</Notice>}
  </section>
}
