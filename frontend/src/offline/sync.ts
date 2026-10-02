import type { Acknowledgement, Command, ErrorBody } from '../api/types'
import { api, ApiError } from '../api/client'
import { db, listEvents, type LocalEvent, type SitrapDB, type LocalStatus } from './db'

type Send = (commands: Command[]) => Promise<Acknowledgement[]>
export async function sendBatch(commands: Command[]): Promise<Acknowledgement[]> {
  // 04 §5; envelope is provisional until B29 OpenAPI confirms exact batch DTO.
  const response = await api.post<{ results: Acknowledgement[] }>('/sync/events', { events: commands })
  if (!Array.isArray(response.results)) throw new Error('La respuesta de sincronización no incluye acuses individuales.')
  return response.results
}
const retryable = (error: ErrorBody) => error.retryable || error.code === 'DEPENDENCY_MISSING'
const now = () => new Date().toISOString()
async function setStatus(store: SitrapDB, entry: LocalEvent, status: LocalStatus, error?: ErrorBody, result?: unknown) {
  await store.events.update(entry.event_id, { status, updated_at: now(), error, result })
}

/** Foreground sync. Never changes an intention's UUID, payload or expected_version. */
export async function syncAccount(accountId: string, send: Send = sendBatch, store: SitrapDB = db): Promise<{ applied: number; waiting: number; rejected: number }> {
  if (!accountId) throw new Error('Se necesita una cuenta autenticada para sincronizar.')
  const all = await listEvents(accountId, store)
  const remaining = all.filter(entry => entry.status !== 'APLICADA' && entry.status !== 'RECHAZADA')
  const byId = new Map(all.map(entry => [entry.event_id, entry]))
  const visiting = new Set<string>()
  const visited = new Set<string>()
  const ordered: LocalEvent[] = []
  function visit(entry: LocalEvent) {
    if (visiting.has(entry.event_id)) throw new Error('Hay un ciclo entre operaciones pendientes. Revisa los registros.')
    if (visited.has(entry.event_id)) return
    visiting.add(entry.event_id)
    for (const parentId of entry.command.depends_on) {
      const parent = byId.get(parentId)
      if (parent && parent.status !== 'APLICADA' && parent.status !== 'RECHAZADA') visit(parent)
    }
    visiting.delete(entry.event_id)
    visited.add(entry.event_id)
    ordered.push(entry)
  }
  remaining.forEach(visit)
  const outcome = { applied: 0, waiting: 0, rejected: 0 }
  for (const entry of ordered) {
    const parents = entry.command.depends_on.map(id => byId.get(id))
    if (parents.some(parent => parent?.status === 'RECHAZADA')) {
      const error = { code: 'DEPENDENCY_REJECTED', message: 'Una operación anterior fue rechazada. Revisa este registro.', retryable: false }
      await setStatus(store, entry, 'RECHAZADA', error); entry.status = 'RECHAZADA'; outcome.rejected++; continue
    }
    if (parents.some(parent => parent && parent.status !== 'APLICADA')) {
      await setStatus(store, entry, 'ESPERA_DEPENDENCIA'); entry.status = 'ESPERA_DEPENDENCIA'; outcome.waiting++; continue
    }
    // Missing parent may already be accepted by server on another device; let server decide.
    await setStatus(store, entry, 'ENVIANDO')
    try {
      const results = await send([entry.command])
      const ack = results.find(result => result.event_id === entry.event_id)
      if (!ack) throw new Error('Falta el acuse individual de la operación.')
      if (ack.status === 'APLICADA') {
        await setStatus(store, entry, 'APLICADA', undefined, ack.result); entry.status = 'APLICADA'; outcome.applied++
      } else if (ack.status === 'RECHAZADA') {
        await setStatus(store, entry, 'RECHAZADA', ack.error ?? { code: 'REJECTED', message: 'Rechazada por el servidor. Revisa el registro.', retryable: false }); entry.status = 'RECHAZADA'; outcome.rejected++
      } else {
        await setStatus(store, entry, 'ESPERA_DEPENDENCIA', ack.error); entry.status = 'ESPERA_DEPENDENCIA'; outcome.waiting++
      }
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.body.code === 'SESSION_EXPIRED' || error.body.code === 'CSRF_FAILED')) {
        await setStatus(store, entry, 'REQUIERE_SESION', error.body); entry.status = 'REQUIERE_SESION'; outcome.waiting++; break
      }
      if (error instanceof ApiError && !retryable(error.body)) {
        await setStatus(store, entry, 'RECHAZADA', error.body); entry.status = 'RECHAZADA'; outcome.rejected++
      } else {
        await setStatus(store, entry, 'PENDIENTE', error instanceof ApiError ? error.body : { code: 'SYNC_UNAVAILABLE', message: 'No se recibió un acuse válido. Reintenta con el mismo UUID.', retryable: true }); entry.status = 'PENDIENTE'; outcome.waiting++; break
      }
    }
  }
  return outcome
}
