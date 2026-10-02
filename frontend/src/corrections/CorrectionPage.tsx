import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useLiveQuery } from 'dexie-react-hooks'
import { useAuth } from '../auth/AuthProvider'
import { useWorkspace } from '../auth/workspace'
import { api, apiMode } from '../api/client'
import { createCommand } from '../api/commands'
import { db, enqueue, getDevice, readCopy, saveCopy } from '../offline/db'
import { syncAccount } from '../offline/sync'
import { useConnection } from '../offline/SyncPanel'
import { Button, Notice } from '../components/ui'

export interface Correction { id: string; transfer_id: string; original_quantity: number; proposed_quantity: number; reason: string; state: 'PENDIENTE' | 'APLICADA' | 'RECHAZADA' | 'RETIRADA'; proposal_version_id: string; approver_transport: string; approver_reception: string; lock_version: number; decisions: { role: 'TRANSPORTE' | 'RECEPCION'; decision: 'ACEPTAR' | 'RECHAZAR'; user_id: string }[] }
const roleLabel = (role: string) => role === 'TRANSPORTE' ? 'Transporte' : 'Recepción'
export function CorrectionPage() {
  const { id } = useParams()
  const { account } = useAuth()
  const { assignment } = useWorkspace()
  const online = useConnection()
  const cache = useQueryClient()
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [reason, setReason] = useState('')
  const [rejecting, setRejecting] = useState(false)
  const [busy, setBusy] = useState(false)
  const copy = useLiveQuery(() => account && id ? readCopy(account.id, 'correction', id) : undefined, [account?.id, id])
  const query = useQuery({ queryKey: ['correction', account?.id, id], queryFn: () => api.request<Correction>(`/corrections/${encodeURIComponent(id!)}`), enabled: !!account && !!id && online, refetchOnWindowFocus: true })
  useEffect(() => { if (query.data && account) void saveCopy(account.id, 'correction', query.data.id, { ...query.data, version_id: query.data.proposal_version_id }).catch(() => setError('No se pudo guardar la propuesta descargada.')) }, [query.data, account?.id])
  const proposal = online ? query.data ?? (copy?.document as Correction | undefined) : copy?.document as Correction | undefined
  const actions = useLiveQuery(() => account && id ? db.events.where('account_id').equals(account.id).filter(item => item.command.entity_id === id && ['CORRECTION_ACCEPT', 'CORRECTION_REJECT'].includes(item.command.type) && item.status !== 'RECHAZADA').toArray() : [], [account?.id, id], [])
  const role = assignment?.role
  const designated = role === 'TRANSPORTE' ? proposal?.approver_transport === account?.id : role === 'RECEPCION' ? proposal?.approver_reception === account?.id : false
  const decided = proposal?.decisions.some(item => item.role === role) || actions.length > 0
  async function decide(decision: 'accept' | 'reject') {
    if (!account || !proposal || !designated || decided || busy) return
    setError(''); setMessage('')
    if (decision === 'reject' && !reason.trim()) { setError('Escribe el motivo del rechazo.'); return }
    setBusy(true)
    try {
      const device = await getDevice(account.id)
      const command = createCommand({ type: decision === 'accept' ? 'CORRECTION_ACCEPT' : 'CORRECTION_REJECT', device_id: device.device_id, entity_id: proposal.id, expected_version: proposal.lock_version, payload: { version_id: proposal.proposal_version_id, ...(decision === 'reject' ? { reason: reason.trim() } : {}) } })
      await enqueue(account.id, command)
      if (online && apiMode === 'http') { await syncAccount(account.id); await cache.invalidateQueries({ queryKey: ['correction', account.id, id] }) }
      const status = await db.events.get(command.event_id)
      setMessage(status?.status === 'APLICADA' ? 'Decisión aceptada por el servidor. Comprueba si aún falta la otra aprobación.' : 'Decisión guardada en este teléfono. No se aplicó ningún cambio hasta recibir acuse del servidor.')
      setRejecting(false)
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  return <section className="stack form"><h1>Corrección de cantidad</h1>
    {apiMode === 'mock' && <Notice tone="warning">Demostración sin decisiones remotas. Una aprobación local nunca cambia la cantidad vigente.</Notice>}
    {query.isPending && online && <Notice>Cargando propuesta…</Notice>}
    {query.isError && !proposal && <Notice tone="error">No pudimos consultar esta propuesta o no tienes permiso. Reintenta con conexión.</Notice>}
    {!proposal && !online && <Notice tone="warning">Necesitas descargar la propuesta antes de decidir sin conexión.</Notice>}
    {proposal && <article className="card stack"><h2>Entrega {proposal.transfer_id}</h2><p className="quantity">{proposal.original_quantity} L → {proposal.proposed_quantity} L</p><p>Motivo: {proposal.reason}</p><p>Estado documental: {proposal.state}. La etapa física de la entrega no se modifica por leer ni decidir esta propuesta.</p>
      {(['TRANSPORTE', 'RECEPCION'] as const).map(roleName => { const decision = proposal.decisions.find(item => item.role === roleName); return <p key={roleName}>{roleLabel(roleName)} · {roleName === 'TRANSPORTE' ? proposal.approver_transport : proposal.approver_reception}: {decision ? decision.decision === 'ACEPTAR' ? 'Aceptó' : 'Rechazó' : 'Pendiente'}</p> })}
      {proposal.state === 'PENDIENTE' && designated && !decided && <div className="stack"><p>Aceptas exactamente el cambio mostrado; tu decisión no confirma la recepción física.</p><div className="row"><Button busy={busy} onClick={() => void decide('accept')}>Aceptar corrección</Button><Button variant="danger" onClick={() => setRejecting(true)}>Rechazar corrección</Button></div>
        {rejecting && <div className="field"><label htmlFor="reject-reason">Motivo del rechazo</label><textarea id="reject-reason" value={reason} onChange={event => setReason(event.target.value)} /><Button busy={busy} onClick={() => void decide('reject')}>Confirmar rechazo</Button></div>}
      </div>}
      {decided && proposal.state === 'PENDIENTE' && <Notice tone="warning">Ya registraste una decisión o hay una pendiente de sincronizar. Falta consultar el estado final del servidor.</Notice>}
      {proposal.state === 'APLICADA' && <Notice tone="success">Ambos aprobaron; la cantidad vigente se actualizó. La recepción física, si faltaba, sigue pendiente.</Notice>}
    </article>}
    {message && <Notice tone="warning">{message}</Notice>}{error && <Notice tone="error">{error}</Notice>}
    <Link to="/sincronizacion">Ver operaciones locales y conflictos</Link>
  </section>
}
