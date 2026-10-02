import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useLiveQuery } from 'dexie-react-hooks'
import { useQuery } from '@tanstack/react-query'
import { api, apiMode } from '../api/client'
import { createCommand } from '../api/commands'
import { useAuth } from '../auth/AuthProvider'
import { useWorkspace } from '../auth/workspace'
import { db, enqueue, getDevice, readCopy, saveCopy } from '../offline/db'
import { Button, Notice } from '../components/ui'
import { ProposeCorrection } from '../corrections/ProposeCorrection'
import { AcceptedMark } from '../components/AcceptedMark'

interface LocalTransfer { version_id: string; lot_id: string; units_presentation: number; destination_id: string; driver_id: string; receiver_id: string; event_id: string; send_event_id?: string }
interface ServerTransfer { id: string; code: string; state: string; lock_version: number; version_id: string; units_presentation: number; origin_name: string; destination_name: string; driver_name: string; receiver_name: string }
export function TransferDetailPage() {
  const { id } = useParams()
  const { account } = useAuth()
  const { assignment } = useWorkspace()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const [revising, setRevising] = useState(false)
  const [reason, setReason] = useState('')
  const [bags, setBags] = useState('')
  const local = useLiveQuery(() => account && id ? readCopy(account.id, 'transfer-draft', id) : undefined, [account?.id, id])
  const draft = local?.document as LocalTransfer | undefined
  const creation = useLiveQuery(() => draft ? db.events.get(draft.event_id) : undefined, [draft?.event_id])
  const sending = useLiveQuery(() => draft?.send_event_id ? db.events.get(draft.send_event_id) : undefined, [draft?.send_event_id])
  const server = useQuery({ queryKey: ['transfer', account?.id, id], queryFn: () => api.request<ServerTransfer>(`/transfers/${encodeURIComponent(id!)}`), enabled: !!account && !!id && !draft && navigator.onLine })
  async function send() {
    if (!account || !id || !draft || draft.send_event_id || busy || assignment?.role !== 'PRODUCCION') return
    setBusy(true); setError('')
    try {
      if (!creation || creation.status === 'RECHAZADA') throw new Error('El borrador fue rechazado o aún no está disponible. Revisa Pendientes.')
      const device = await getDevice(account.id)
      const command = createCommand({ type: 'TRANSFER_SEND', entity_id: id, device_id: device.device_id, expected_version: 1, depends_on: [draft.event_id], payload: { version_id: draft.version_id } })
      await enqueue(account.id, command)
      await saveCopy(account.id, 'transfer-draft', id, { ...draft, send_event_id: command.event_id })
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  async function change(kind: 'revise' | 'cancel') {
    if (!server.data || !account || !id || !navigator.onLine || busy || assignment?.role !== 'PRODUCCION') return
    setBusy(true); setError('')
    try {
      if (!reason.trim()) throw new Error('Explica el motivo del cambio.')
      const device = await getDevice(account.id)
      if (kind === 'revise' && (!/^[1-9]\d*$/.test(bags) || !Number.isSafeInteger(Number(bags)))) throw new Error('La cantidad debe ser un número entero positivo de bolsas.')
      const amount = kind === 'revise' ? Number(bags) : undefined
      const command = createCommand({ type: kind === 'revise' ? 'TRANSFER_REVISE' : 'TRANSFER_CANCEL', entity_id: id, device_id: device.device_id, expected_version: server.data.lock_version, payload: { version_id: server.data.version_id, ...(kind === 'revise' ? { new_version_id: crypto.randomUUID(), units_presentation: amount } : {}), reason: reason.trim() } })
      // These commands are ONLINE only (04 §5): do not enqueue locally.
      await api.post(`/transfers/${encodeURIComponent(id)}/${kind}`, command)
      await server.refetch()
      setEditing(false); setRevising(false); setReason('')
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  if (!id) return <Notice tone="error">Entrega no identificada.</Notice>
  return <section className="stack form"><h1>Detalle de entrega</h1>
    {apiMode === 'mock' && <Notice tone="warning">Demostración sin servidor. La solicitud NO se notifica al conductor; solo queda en este teléfono.</Notice>}
    {local === undefined && server.isPending && <Notice>Cargando entrega…</Notice>}
    {draft && <article className="card stack"><p>Documento borrador · Lote {draft.lot_id}</p><p className="quantity">{draft.units_presentation} bolsas · {draft.units_presentation} L</p><p>Destino {draft.destination_id} · Conductor {draft.driver_id} · Receptor {draft.receiver_id}</p>
      <p>Creación: {creation?.status === 'APLICADA' ? 'Guardada en el sistema' : 'Guardada en este teléfono, sin acuse central'}.</p>
      {!draft.send_event_id && assignment?.role === 'PRODUCCION' && <Button busy={busy} onClick={() => void send()}>Enviar solicitud a transporte</Button>}
      {sending && <Notice tone={sending.status === 'APLICADA' ? 'success' : 'warning'}>{sending.status === 'APLICADA' ? <AcceptedMark label="Solicitud aceptada por el servidor. El aviso a transporte depende del backend." /> : sending.status === 'RECHAZADA' ? `Solicitud rechazada: ${sending.error?.message ?? 'revisa el registro'}` : 'Envío guardado en este teléfono, pendiente de aceptar por el servidor. Nadie más lo ve todavía.'}</Notice>}
    </article>}
    {!draft && server.data && <article className="card stack"><h2>{server.data.code}</h2><p>{server.data.state} · Versión {server.data.lock_version}</p><p className="quantity">{server.data.units_presentation} bolsas · {server.data.units_presentation} L</p><p>{server.data.origin_name} → {server.data.destination_name}</p><p>Conductor {server.data.driver_name} · Receptor {server.data.receiver_name}</p>
      {server.data.state === 'PENDIENTE_RECOGIDA' && assignment?.role === 'PRODUCCION' && <div className="row"><Button variant="secondary" onClick={() => { setEditing(true); setRevising(true); setBags(String(server.data?.units_presentation)) }}>Modificar solicitud</Button><Button variant="danger" onClick={() => { setEditing(true); setRevising(false) }}>Cancelar solicitud</Button></div>}
      {editing && <section className="stack"><h3>{revising ? 'Modificar antes de recogida' : 'Cancelar antes de recogida'}</h3><p>Si el conductor confirmó mientras editabas, el servidor rechazará esta versión y tendrás que consultar el estado actual.</p>
        {revising && <div className="field"><label htmlFor="revised-bags">Bolsas de 1 L propuestas</label><input id="revised-bags" inputMode="numeric" value={bags} onChange={event => setBags(event.target.value)} /></div>}
        <div className="field"><label htmlFor="change-reason">Motivo obligatorio</label><textarea id="change-reason" value={reason} onChange={event => setReason(event.target.value)} /></div>
        <div className="row"><Button busy={busy} onClick={() => void change(revising ? 'revise' : 'cancel')}>{revising ? 'Publicar revisión' : 'Confirmar cancelación'}</Button><Button variant="secondary" onClick={() => setEditing(false)}>Volver</Button></div>
      </section>}
    </article>}
    {!draft && server.data && ['EN_CAMINO', 'RECIBIDO'].includes(server.data.state) && assignment?.role === 'PRODUCCION' && <ProposeCorrection transfer={server.data} />}
    {!draft && server.isError && <Notice tone="error">No se pudo consultar esta entrega o no tienes autorización. Un aviso antiguo no acredita permisos actuales.</Notice>}
    {error && <Notice tone="error">{error}</Notice>}
    <Link to="/sincronizacion">Ver estado de sincronización</Link>
  </section>
}
