import { useState } from 'react'
import { api } from '../api/client'
import { Button, Notice } from '../components/ui'
import type { Module } from './salesTypes'

export function SaleCatalog({ modules, onSaved }: { modules: Module[]; onSaved: () => void }) {
  const [id, setId] = useState('')
  const [name, setName] = useState('')
  const [active, setActive] = useState(true)
  const [components, setComponents] = useState([{ category: 'MACHO', quality: 'A', quantity: 1 }, { category: 'HEMBRA', quality: 'A', quantity: 3 }])
  const [reason, setReason] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  return <details className="card"><summary>Catálogo de módulos reproductivos</summary><form className="stack form" onSubmit={async e => {
    e.preventDefault(); setBusy(true); setMessage('')
    try { const key = id || crypto.randomUUID(); setId(key); await api.post('/cuyes/sales/modules', { id: key, name, active, components, reason }); onSaved(); setMessage('Módulo guardado. Las órdenes anteriores mantienen su receta.') }
    catch (error) { setMessage((error as Error).message) } finally { setBusy(false) }
  }}>
    <label>Editar módulo<select aria-label="Editar módulo" value={id} onChange={e => { const m = modules.find(m => m.id === e.target.value); setId(e.target.value); if (m) { setName(m.name); setActive(m.active); setComponents(m.components) } }}><option value="">Nuevo módulo</option>{modules.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
    <label>Nombre del módulo<input required value={name} onChange={e => setName(e.target.value)} maxLength={150} /></label>
    {components.map((c, index) => <fieldset className="card stack" key={index}><legend>Componente {index + 1}</legend><label>Sexo del componente<select aria-label="Sexo del componente" value={c.category} onChange={e => setComponents(components.map((v, i) => i === index ? { ...v, category: e.target.value } : v))}><option>MACHO</option><option>HEMBRA</option></select></label><label>Calidad del componente<select aria-label="Calidad del componente" value={c.quality} onChange={e => setComponents(components.map((v, i) => i === index ? { ...v, quality: e.target.value } : v))}>{['A', 'B', 'C', 'SIN_CLASIFICAR'].map(q => <option key={q}>{q}</option>)}</select></label><label>Cantidad por módulo<input required type="number" min="1" step="1" value={c.quantity} onChange={e => setComponents(components.map((v, i) => i === index ? { ...v, quantity: Number(e.target.value) } : v))} /></label><Button type="button" variant="secondary" onClick={() => setComponents(components.filter((_, i) => i !== index))}>Quitar componente</Button></fieldset>)}
    <Button type="button" variant="secondary" onClick={() => setComponents([...components, { category: 'HEMBRA', quality: 'A', quantity: 1 }])}>Añadir componente</Button>
    <label><input type="checkbox" checked={active} onChange={e => setActive(e.target.checked)} /> Módulo activo</label><label>Motivo de catálogo<input required value={reason} onChange={e => setReason(e.target.value)} /></label>
    <Button type="submit" busy={busy}>Guardar módulo</Button>{message && <Notice>{message}</Notice>}
  </form></details>
}
