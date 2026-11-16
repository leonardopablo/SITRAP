import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { Button, Notice } from '../components/ui'
import type { Availability, Module, SalesOptions, SaleType } from './salesTypes'

const blank = () => ({ id: crypto.randomUUID(), kind: 'UNIDAD', units: 1, category: 'MACHO', quality: 'B', module_id: '', weight_kg: '1.000', weight_basis: 'VIVO', unit_price: '1.00' })
export function NewSaleForm({ options, modules, perform }: { options: SalesOptions; modules: Module[]; perform: (type: SaleType, payload: Record<string, unknown>, id?: string) => Promise<boolean> }) {
  const [id, setId] = useState(crypto.randomUUID())
  const [center, setCenter] = useState('')
  const [client, setClient] = useState('')
  const [contact, setContact] = useState('')
  const [reference, setReference] = useState('')
  const [mode, setMode] = useState('DIRECTO')
  const [point, setPoint] = useState('')
  const [currency, setCurrency] = useState('PEN')
  const [reason, setReason] = useState('')
  const [items, setItems] = useState([blank()])
  const availability = useQuery({ queryKey: ['sale-availability', center], queryFn: () => api.request<Availability>(`/cuyes/sales/availability?workspace=ADMIN&center_id=${center}`), enabled: !!center })
  const patch = (index: number, p: Partial<ReturnType<typeof blank>>) => setItems(items.map((v, i) => i === index ? { ...v, ...p } : v))
  const total = items.reduce((sum, i) => sum + Number(i.unit_price) * Number(i.kind === 'PESO' ? i.weight_kg : i.units), 0)
  return <details className="card"><summary>Nueva orden de venta</summary><form className="stack form" onSubmit={async e => {
    e.preventDefault()
    const saved = await perform('SALE_CREATE', { center_id: center, client_name: client, client_contact: contact, client_reference: reference, mode, ...(mode === 'PUNTO' ? { point_id: point } : {}), currency, reason,
      items: items.map(i => ({ id: i.id, kind: i.kind, units: i.units, unit_price: i.unit_price, ...(i.kind === 'MODULO' ? { module_id: i.module_id } : { category: i.category, quality: i.quality }), ...(i.kind === 'PESO' ? { weight_kg: i.weight_kg, weight_basis: i.weight_basis } : {}) })) }, id)
    if (saved) { setId(crypto.randomUUID()); setClient(''); setContact(''); setReference(''); setItems([blank()]); setReason('') }
  }}>
    <label>Centro de la venta<select required aria-label="Centro de la venta" value={center} onChange={e => setCenter(e.target.value)}><option value="">Selecciona un solo centro</option>{options.centers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
    {availability.data && <Notice>Disponibilidad referencial: {availability.data.buckets.map(b => `${b.category}/${b.quality}: ${b.available}`).join(' · ')}. Módulos: {availability.data.modules.map(m => `${m.name}: ${m.offerable}`).join(' · ')}. No reserva hasta confirmar.</Notice>}
    <label>Nombre del cliente<input required value={client} onChange={e => setClient(e.target.value)} maxLength={150} autoComplete="off" /></label><label>Contacto indispensable<input value={contact} onChange={e => setContact(e.target.value)} maxLength={100} autoComplete="off" /></label><label>Referencia del cliente (opcional)<input value={reference} onChange={e => setReference(e.target.value)} maxLength={100} autoComplete="off" /></label>
    <label>Modalidad<select aria-label="Modalidad" value={mode} onChange={e => setMode(e.target.value)}><option value="DIRECTO">Recojo directo en el centro</option><option value="PUNTO">Conductor a punto de venta</option></select></label>
    {mode === 'PUNTO' && <label>Punto de venta<select required aria-label="Punto de venta" value={point} onChange={e => setPoint(e.target.value)}><option value="">Selecciona</option>{options.points.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>}
    <label>Moneda<select aria-label="Moneda" value={currency} onChange={e => setCurrency(e.target.value)}><option>PEN</option><option>USD</option></select></label>
    {items.map((item, index) => <fieldset className="card stack" key={item.id}><legend>Ítem {index + 1}</legend>
      <label>Tipo de ítem<select aria-label="Tipo de ítem" value={item.kind} onChange={e => patch(index, { kind: e.target.value })}><option value="UNIDAD">Cuy por unidad</option><option value="PESO">Cuy por peso</option><option value="MODULO">Módulo reproductivo</option></select></label>
      {item.kind === 'MODULO' ? <label>Módulo<select required aria-label="Módulo" value={item.module_id} onChange={e => patch(index, { module_id: e.target.value })}><option value="">Selecciona receta</option>{modules.filter(m => m.active).map(m => <option key={m.id} value={m.id}>{m.name} · {m.components.map(c => `${c.quantity} ${c.category}/${c.quality}`).join(' + ')}</option>)}</select></label> : <><label>Sexo autorizado<select aria-label="Sexo autorizado" value={item.category} onChange={e => patch(index, { category: e.target.value })}><option>MACHO</option><option>HEMBRA</option></select></label><label>Calidad acordada<select aria-label="Calidad acordada" value={item.quality} onChange={e => patch(index, { quality: e.target.value })}>{['A', 'B', 'C', 'SIN_CLASIFICAR'].map(q => <option key={q}>{q}</option>)}</select></label></>}
      <label>{item.kind === 'MODULO' ? 'Número de módulos' : 'Número de animales a reservar y retirar'}<input required type="number" min="1" step="1" value={item.units} onChange={e => patch(index, { units: Number(e.target.value) })} /></label>
      {item.kind === 'PESO' && <><label>Peso acordado para cobrar (KG, 3 decimales)<input required type="number" min=".001" step=".001" value={item.weight_kg} onChange={e => patch(index, { weight_kg: e.target.value })} /></label><label>Base del peso<select aria-label="Base del peso" value={item.weight_basis} onChange={e => patch(index, { weight_basis: e.target.value })}><option value="VIVO">Peso vivo</option><option value="BENEFICIADO">Peso beneficiado declarado (sin módulo de faenado)</option></select></label></>}
      <label>Precio acordado por {item.kind === 'PESO' ? 'KG' : item.kind === 'MODULO' ? 'módulo' : 'animal'}<input required type="number" min=".01" step=".01" value={item.unit_price} onChange={e => patch(index, { unit_price: e.target.value })} /></label>
      {items.length > 1 && <Button type="button" variant="secondary" onClick={() => setItems(items.filter((_, i) => i !== index))}>Quitar ítem</Button>}
    </fieldset>)}
    <Button type="button" variant="secondary" onClick={() => setItems([...items, blank()])}>Añadir ítem</Button><p>Total referencial: {currency} {total.toFixed(2)}. El servidor confirma redondeo e importe.</p>
    <label>Motivo de solicitud<input required value={reason} onChange={e => setReason(e.target.value)} maxLength={500} /></label><Button type="submit">Solicitar venta (todavía sin reserva)</Button>
  </form></details>
}
