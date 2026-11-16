import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Page } from '../api/types'
import { Button, Notice } from '../components/ui'
import { purposes, type Pen, type Shed } from './types'

interface Config { centers: { id: string; code: string; name: string }[]; enabled_centers: string[]; grants: { id: string; shed_id: string; assignment_id: string; active: boolean }[]; policies: { id: string; center_id: string; reproductive_months: number; minimum_weaned_per_female: string }[] }
interface Assignment { id: string; user_id: string; role: string; location_id: string; ends_at: string | null }
export function ConfigPanel({ accountId, pens, sheds, onSaved }: { accountId: string; pens: Pen[]; sheds: Shed[]; onSaved: () => void }) {
  const config = useQuery({ queryKey: ['cuyes-config', accountId], queryFn: () => api.request<Config>('/cuyes/config') })
  const assignments = useQuery({ queryKey: ['cuyes-assignments', accountId], queryFn: async () => {
    const rows: Assignment[] = []
    let offset = 0
    while (true) {
      const p = await api.request<Page<Assignment>>(`/role-assignments?limit=200&offset=${offset}`)
      rows.push(...p.results)
      if (!p.next) return rows
      offset += p.results.length
      if (!p.results.length) throw new Error('Paginación incompleta.')
    }
  } })
  const [resource, setResource] = useState('enable')
  const [center, setCenter] = useState('')
  const [shed, setShed] = useState('')
  const [edit, setEdit] = useState('')
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [capacity, setCapacity] = useState(50)
  const [purpose, setPurpose] = useState('MATERNIDAD')
  const [assignment, setAssignment] = useState('')
  const [active, setActive] = useState(true)
  const [months, setMonths] = useState(13)
  const [threshold, setThreshold] = useState('1.00')
  const [reason, setReason] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  async function save() {
    setBusy(true); setMessage('')
    try {
      const base = { resource, id: edit || crypto.randomUUID(), reason, active }
      let payload: Record<string, unknown> = base
      if (resource === 'enable') payload = { ...base, center_id: center }
      if (resource === 'shed') payload = { ...base, center_id: center, code, name }
      if (resource === 'pen') payload = { ...base, shed_id: shed, code, capacity, purpose }
      if (resource === 'grant') {
        const existing = config.data?.grants.find(g => g.shed_id === shed && g.assignment_id === assignment)
        payload = { ...base, id: existing?.id ?? base.id, shed_id: shed, assignment_id: assignment }
      }
      if (resource === 'policy') {
        const existing = config.data?.policies.find(p => p.center_id === center)
        payload = { ...base, id: existing?.id ?? base.id, center_id: center, reproductive_months: months, minimum_weaned_per_female: threshold }
      }
      await api.post('/cuyes/config', payload)
      await config.refetch(); onSaved(); setMessage('Configuración guardada y auditada.')
    } catch (e) { setMessage((e as Error).message) } finally { setBusy(false) }
  }
  return <details className="card stack"><summary>Configuración de Cuyes (ADMIN)</summary>
    <p>Usa los centros existentes. Primero asigna GALPONERO por centro en Cuentas y después autoriza sus galpones aquí.</p>
    <form className="stack form" onSubmit={e => { e.preventDefault(); void save() }}>
      <label>Configurar<select value={resource} onChange={e => { setResource(e.target.value); setEdit(''); setMessage('') }}><option value="enable">Habilitación por centro</option><option value="shed">Galpón</option><option value="pen">Poza</option><option value="grant">Galpones del galponero</option><option value="policy">Umbrales de alertas</option></select></label>
      {['enable', 'shed', 'policy'].includes(resource) && <label>Centro existente<select required value={center} onChange={e => setCenter(e.target.value)}><option value="">Selecciona</option>{config.data?.centers.map(c => <option key={c.id} value={c.id}>{c.name} · {c.code}{config.data.enabled_centers.includes(c.id) ? ' · habilitado' : ''}</option>)}</select></label>}
      {resource === 'shed' && <label>Registro<select value={edit} onChange={e => { const s = sheds.find(s => s.id === e.target.value); setEdit(e.target.value); if (s) { setCenter(s.center_id); setCode(s.code); setName(s.name); setActive(s.active) } }}><option value="">Crear galpón nuevo</option>{sheds.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>}
      {(resource === 'pen' || resource === 'grant') && <label>Galpón<select required value={shed} onChange={e => setShed(e.target.value)}><option value="">Selecciona</option>{sheds.map(s => <option key={s.id} value={s.id}>{s.name} · {s.code}</option>)}</select></label>}
      {resource === 'pen' && <label>Registro<select value={edit} onChange={e => { const p = pens.find(p => p.id === e.target.value); setEdit(e.target.value); if (p) { setShed(p.shed_id); setCode(p.code); setCapacity(p.capacity); setPurpose(p.purpose); setActive(p.active) } }}><option value="">Crear poza nueva</option>{pens.map(p => <option key={p.id} value={p.id}>{p.code}</option>)}</select></label>}
      {(resource === 'shed' || resource === 'pen') && <label>Código físico<input required pattern="[A-Z0-9][A-Z0-9_-]*" maxLength={resource === 'shed' ? 32 : 40} value={code} onChange={e => setCode(e.target.value.toUpperCase())} placeholder={resource === 'pen' ? 'CAN-G1-P01' : 'G1'} /></label>}
      {resource === 'shed' && <label>Nombre<input required value={name} onChange={e => setName(e.target.value)} /></label>}
      {resource === 'pen' && <><label>Capacidad máxima<input required type="number" min="1" step="1" value={capacity} onChange={e => setCapacity(Number(e.target.value))} /></label><label>Propósito<select value={purpose} onChange={e => setPurpose(e.target.value)}>{Object.entries(purposes).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label></>}
      {resource === 'grant' && <label>Asignación GALPONERO del centro<select required value={assignment} onChange={e => setAssignment(e.target.value)}><option value="">Selecciona</option>{assignments.data?.filter(a => a.role === 'GALPONERO' && a.location_id === sheds.find(s => s.id === shed)?.center_id && (!a.ends_at || Date.parse(a.ends_at) > Date.now())).map(a => <option key={a.id} value={a.id}>Cuenta {a.user_id} · asignación {a.id.slice(0, 8)}</option>)}</select></label>}
      {resource === 'policy' && <><label>Antigüedad reproductiva en meses<input type="number" min="1" max="60" value={months} onChange={e => setMonths(Number(e.target.value))} /></label><p>Referencia 12–14 meses. Solo genera revisión; no reclasifica animales.</p><label>Umbral mensual de destetados por hembra<input type="number" min="0" step="0.01" value={threshold} onChange={e => setThreshold(e.target.value)} /></label></>}
      {resource !== 'policy' && <label><input type="checkbox" checked={active} onChange={e => setActive(e.target.checked)} /> Activo / habilitado (desmarcar conserva el historial)</label>}
      <label>Motivo<input required value={reason} onChange={e => setReason(e.target.value)} maxLength={500} /></label>
      <Button type="submit" busy={busy} disabled={!navigator.onLine}>Guardar configuración</Button>
    </form>{config.isError && <Notice tone="error">No se pudo cargar configuración.</Notice>}{message && <Notice>{message}</Notice>}
  </details>
}
