import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiMode } from '../api/client'
import type { Page } from '../api/types'
import { useAuth } from '../auth/AuthProvider'
import { getDevice } from '../offline/db'
import { useConnection } from '../offline/SyncPanel'
import type { AssignmentOptions } from '../transfers/types'
import type { OperationalTransfer } from '../transfers/TransportToday'
import { Button, Notice } from '../components/ui'

export function ReassignReceiver() {
  const { account } = useAuth()
  const online = useConnection()
  const cache = useQueryClient()
  const [transferId, setTransferId] = useState('')
  const [receiverId, setReceiverId] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const transfers = useQuery({ queryKey: ['admin-reassign-transfers', account?.id], queryFn: () => api.request<Page<OperationalTransfer>>('/transfers'), enabled: !!account && online })
  const chosen = transfers.data?.results.find(item => item.id === transferId)
  const options = useQuery({ queryKey: ['admin-receiver-options', account?.id, transferId], queryFn: () => api.request<AssignmentOptions>(`/assignment-options?origin_id=${encodeURIComponent(transferId)}`), enabled: !!chosen && online })
  const allowed = chosen?.state === 'EN_CAMINO' && !chosen.correction_pending
  async function reassign() {
    if (!account || !chosen || !allowed || !online || busy) return
    setError(''); setMessage('')
    if (!reason.trim() || !options.data?.receivers.some(item => item.id === receiverId) || options.data.receivers.find(item => item.id === receiverId)?.name === chosen.receiver_name) { setError('Elige otro receptor autorizado y explica el motivo.'); return }
    setBusy(true)
    try {
      const device = await getDevice(account.id)
      // B26 administrative endpoint, not the TRANSFER_REVISE business command.
      await api.post(`/transfers/${encodeURIComponent(chosen.id)}/reassign-receiver`, { event_id: crypto.randomUUID(), device_id: device.device_id, occurred_at: new Date().toISOString(), expected_version: chosen.lock_version, payload: { receiver_id: receiverId, reason: reason.trim() } })
      await cache.invalidateQueries({ queryKey: ['admin-reassign-transfers', account.id] })
      setMessage(apiMode === 'mock' ? 'Reasignación simulada. No se enviaron avisos reales.' : 'Reasignación aceptada por el servidor; el conductor histórico permanece.')
      setTransferId(''); setReceiverId(''); setReason('')
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  return <section className="stack form"><h1>Reasignar receptor</h1>
    {apiMode === 'mock' && <Notice tone="warning">Cambios de demostración, no reflejados en el servidor real.</Notice>}
    <p>Solo una entrega EN_CAMINO, antes de recepción y sin ninguna solicitud de corrección histórica. No altera cantidad, conductor que recogió ni conformidades previas.</p>
    <div className="field"><label htmlFor="reassign-transfer">Entrega</label><select id="reassign-transfer" value={transferId} onChange={event => { setTransferId(event.target.value); setReceiverId('') }}><option value="">Selecciona</option>{transfers.data?.results.map(item => <option value={item.id} key={item.id}>{item.code} · {item.state}</option>)}</select></div>
    {chosen && <p>Receptor actual: {chosen.receiver_name}. Conductor histórico: {chosen.driver_name}. Cantidad: {chosen.units_presentation} L.</p>}
    {chosen && !allowed && <Notice tone="warning">Esta entrega no puede reasignarse: debe estar en camino y no tener corrección pendiente. El servidor comprobará además toda solicitud histórica.</Notice>}
    {chosen && allowed && <><div className="field"><label htmlFor="new-receiver">Nuevo receptor</label><select id="new-receiver" value={receiverId} onChange={event => setReceiverId(event.target.value)}><option value="">Selecciona</option>{options.data?.receivers.filter(item => item.name !== chosen.receiver_name).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>
      <div className="field"><label htmlFor="reassign-reason">Motivo obligatorio</label><textarea id="reassign-reason" value={reason} onChange={event => setReason(event.target.value)} /></div>
      <Button busy={busy} disabled={!online || options.isPending || !receiverId || !reason.trim()} onClick={() => void reassign()}>Guardar reasignación</Button></>}
    {error && <Notice tone="error">{error}</Notice>}{message && <Notice>{message}</Notice>}
  </section>
}
