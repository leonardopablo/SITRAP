import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { api, apiMode } from '../api/client'
import type { Page } from '../api/types'
import { useAuth } from '../auth/AuthProvider'
import { useWorkspace } from '../auth/workspace'
import { Button, Field, Notice } from '../components/ui'
import { useConnection } from '../offline/SyncPanel'
import type { Animal } from './types'

const schema = z.object({ code: z.string().trim().min(1, 'Escribe un código.').max(40), name: z.string().trim().max(100), status: z.enum(['ACTIVO', 'INACTIVO']) })
type Form = z.infer<typeof schema>
export function AnimalsPage() {
  const { account } = useAuth()
  const { assignment } = useWorkspace()
  const online = useConnection()
  const cache = useQueryClient()
  const [editing, setEditing] = useState<Animal | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const [speciesId, setSpeciesId] = useState('')
  const key = ['animals', account?.id, assignment?.id]
  const animals = useQuery({ queryKey: key, queryFn: () => api.request<Page<Animal>>('/animals'), enabled: !!account && !!assignment && online })
  const species = useQuery({ queryKey: ['animal-species', account?.id], queryFn: () => api.request<Page<{ id: string; name: string; active: boolean }>>('/species'), enabled: !!account && online })
  const detail = useQuery({ queryKey: ['animal', account?.id, selected], queryFn: () => api.request<Animal>(`/animals/${encodeURIComponent(selected!)}`), enabled: !!selected && online })
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { code: '', name: '', status: 'ACTIVO' } })
  const centerId = assignment?.location_id
  async function save(values: Form) {
    setError(''); setMessage('')
    if (!online) { setError('Alta y edición de vacas requieren conexión.'); return }
    try {
      if (editing) await api.patch<Animal>(`/animals/${encodeURIComponent(editing.id)}`, { name: values.name, status: values.status })
      else if (centerId && (speciesId || species.data?.results.filter(item => item.active).length === 1)) await api.post<Animal>('/animals', { id: crypto.randomUUID(), code: values.code, name: values.name, species_id: speciesId || species.data!.results.find(item => item.active)!.id, sex: 'HEMBRA', center_id: centerId, stay_id: crypto.randomUUID(), starts_on: new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()) })
      else if (centerId) throw new Error('Selecciona la especie autorizada antes de registrar.')
      else { setError('Elige primero un centro autorizado.'); return }
      await cache.invalidateQueries({ queryKey: ['animals', account?.id] })
      if (editing) await cache.invalidateQueries({ queryKey: ['animal', account?.id, editing.id] })
      setMessage(apiMode === 'mock' ? 'Cambio simulado en memoria. No se registró en SITRAP.' : editing ? 'Cambios guardados en el sistema.' : 'Vaca registrada en el sistema.')
      setFormOpen(false); setEditing(null); reset()
    } catch (cause) { setError((cause as Error).message) }
  }
  function edit(item: Animal) { setSelected(null); setEditing(item); reset({ code: item.code, name: item.name ?? '', status: item.status }); setFormOpen(true) }
  return <section className="stack"><h1>Vacas</h1><p>Lista del centro autorizado. Los movimientos entre centros requieren administración y no se hacen desde esta pantalla.</p>
    {apiMode === 'mock' && <Notice tone="warning">Vacas de demostración en memoria. No están conectadas al servidor.</Notice>}
    <Button disabled={!online || !centerId} onClick={() => { setEditing(null); reset({ code: '', name: '', status: 'ACTIVO' }); setFormOpen(true); setSelected(null) }}>Registrar vaca</Button>
    {!online && <Notice tone="warning">Sin conexión. Alta y edición no disponibles; prepara datos para consultarlos offline en una fase posterior.</Notice>}
    {formOpen && <form className="card stack form" onSubmit={handleSubmit(save)}><h2>{editing ? 'Editar vaca' : 'Registrar vaca'}</h2>
      <Field label="Código de vaca" {...register('code')} error={errors.code?.message} />
      <Field label="Nombre (opcional)" {...register('name')} error={errors.name?.message} />
      {!editing && <div className="field"><label htmlFor="animal-species">Especie</label><select id="animal-species" value={speciesId || (species.data?.results.filter(item => item.active).length === 1 ? species.data.results.find(item => item.active)!.id : '')} onChange={event => setSpeciesId(event.target.value)}><option value="">Selecciona especie</option>{species.data?.results.filter(item => item.active).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>}
      {editing && <div className="field"><label htmlFor="animal-status">Estado</label><select id="animal-status" {...register('status')}><option value="ACTIVO">Activa</option><option value="INACTIVO">Inactiva</option></select></div>}
      <p className="help">Centro {assignment?.location_name}. No registra producción ni lactancia.</p>
      {error && <Notice tone="error">{error}</Notice>}
      <div className="row"><Button busy={isSubmitting} type="submit">{editing ? 'Guardar cambios' : 'Registrar vaca'}</Button><Button variant="secondary" type="button" onClick={() => setFormOpen(false)}>Cancelar</Button></div>
    </form>}
    {message && <Notice tone="success">{message}</Notice>}
    {animals.isPending && <Notice>Cargando vacas…</Notice>}
    {animals.isError && <Notice tone="error">No pudimos consultar las vacas. <Button variant="secondary" onClick={() => void animals.refetch()}>Reintentar</Button></Notice>}
    {animals.data?.results.length === 0 && <p>No hay vacas registradas en este centro.</p>}
    {animals.data?.results.map(item => <article key={item.id} className="card"><h2>{item.code}{item.name ? ` · ${item.name}` : ''}</h2><p>{item.status === 'ACTIVO' ? 'Activa' : 'Inactiva'} · {item.center_name}</p><div className="row"><Button variant="secondary" onClick={() => setSelected(item.id)}>Ver detalle</Button><Button variant="secondary" onClick={() => edit(item)}>Editar</Button></div></article>)}
    {selected && <section className="card"><h2>Detalle de vaca</h2>{detail.isPending ? <p>Cargando…</p> : detail.isError ? <Notice tone="error">No tienes acceso a este detalle o no está disponible.</Notice> : <p>{detail.data?.code} · {detail.data?.name || 'Sin nombre'} · {detail.data?.center_name}</p>}
      <p>La producción por período se incorpora en F28.</p><Button variant="secondary" onClick={() => setSelected(null)}>Cerrar detalle</Button></section>}
    {animals.data?.next && <Notice>Hay más vacas; la paginación se conectará al contrato real B12.</Notice>}
  </section>
}
