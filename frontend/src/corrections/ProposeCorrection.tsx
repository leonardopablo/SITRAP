import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiMode } from '../api/client'
import { createCommand } from '../api/commands'
import { useAuth } from '../auth/AuthProvider'
import { useWorkspace } from '../auth/workspace'
import { getDevice } from '../offline/db'
import { useConnection } from '../offline/SyncPanel'
import { Button, Notice } from '../components/ui'
import type { OperationalTransfer } from '../transfers/TransportToday'

interface Correction { id: string; transfer_id: string; original_quantity: number; proposed_quantity: number; reason: string; state: string; approver_transport: string; approver_reception: string }
export function ProposeCorrection({ transfer }: { transfer: OperationalTransfer }) {
  const { account } = useAuth()
  const { assignment } = useWorkspace()
  const online = useConnection()
  const cache = useQueryClient()
  const [quantity, setQuantity] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [created, setCreated] = useState<Correction | null>(null)
  const existing = useQuery({ queryKey: ['corrections', account?.id, transfer.id], queryFn: () => api.request<{ results: Correction[] }>('/corrections'), enabled: !!account && online })
  const pending = existing.data?.results.find(item => item.transfer_id === transfer.id && item.state === 'PENDIENTE')
  async function propose() {
    if (!account || assignment?.role !== 'PRODUCCION' || !online || busy || pending) return
    setError('')
    if (!/^[1-9]\d*$/.test(quantity) || !Number.isSafeInteger(Number(quantity))) { setError('Indica un número entero positivo de bolsas de 1 L.'); return }
    if (Number(quantity) === transfer.units_presentation) { setError('La cifra propuesta debe ser distinta de la vigente.'); return }
    if (!reason.trim()) { setError('Escribe un motivo para esta corrección.'); return }
    setBusy(true)
    try {
      const device = await getDevice(account.id)
      const command = createCommand({ type: 'CORRECTION_CREATE', entity_id: transfer.id, device_id: device.device_id, expected_version: transfer.lock_version, payload: { correction_id: crypto.randomUUID(), proposal_version_id: crypto.randomUUID(), new_quantity: Number(quantity), reason: reason.trim() } })
      // Online-only command: never enter offline outbox.
      const result = await api.post<{ result: Correction }>(`/transfers/${encodeURIComponent(transfer.id)}/corrections`, command)
      setCreated(result.result)
      await cache.invalidateQueries({ queryKey: ['corrections', account.id] })
      await cache.invalidateQueries({ queryKey: ['transfer', account.id, transfer.id] })
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  return <section className="card stack"><h2>Solicitar corrección de cantidad</h2>
    {apiMode === 'mock' && <Notice tone="warning">Propuesta simulada solo en memoria. No avisa a transporte ni recepción reales.</Notice>}
    <p>Cantidad vigente: <strong>{transfer.units_presentation} bolsas · {transfer.units_presentation} L</strong>. La entrega conserva su etapa logística.</p>
    <p>Se actualizará solo si transporte y recepción aprueban exactamente esta cifra. Aprobar antes de recibir no confirma la recepción física.</p>
    {pending || created ? <Notice tone="warning">Propuesta pendiente {pending?.id ?? created?.id}. Cantidad vigente sin cambios. <Link to={`/correcciones/${pending?.id ?? created?.id}`}>Ver propuesta y aprobadores</Link></Notice> : <>
      <div className="field"><label htmlFor="correction-quantity">Nueva cantidad de bolsas de 1 L</label><input id="correction-quantity" inputMode="numeric" value={quantity} onChange={event => setQuantity(event.target.value)} /></div>
      <div className="field"><label htmlFor="correction-reason">Motivo obligatorio</label><textarea id="correction-reason" value={reason} onChange={event => setReason(event.target.value)} /></div>
      {error && <Notice tone="error">{error}</Notice>}
      <Button busy={busy} disabled={!online || existing.isPending} onClick={() => void propose()}>Enviar propuesta a dos aprobadores</Button>
    </>}
  </section>
}
