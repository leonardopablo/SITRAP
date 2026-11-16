import { api, ApiError } from '../api/client'
import { createCommand } from '../api/commands'
import type { Acknowledgement, Command, Page } from '../api/types'
import { db, enqueue, getDevice, listEvents, type SitrapDB } from '../offline/db'
import { syncAccount } from '../offline/sync'
import type { CuyType, Pen } from './types'

export async function allPages<T>(path: string): Promise<T[]> {
  const rows: T[] = []
  let next: string | null = path
  const visited = new Set<string>()
  while (next) {
    if (visited.has(next)) throw new Error('Paginación repetida.')
    visited.add(next)
    const page: Page<T> = await api.request<Page<T>>(next)
    rows.push(...page.results)
    if (page.next) {
      const url = new URL(page.next, window.location.origin)
      if (url.origin !== window.location.origin || !url.pathname.startsWith('/api/v1/cuyes/')) throw new Error('Página no autorizada.')
      next = url.pathname.replace('/api/v1', '') + url.search
    } else next = null
  }
  return rows
}

export async function makeCuyCommand(accountId: string, type: CuyType, payload: Record<string, unknown>): Promise<Command> {
  const device = await getDevice(accountId)
  if (navigator.onLine && !device.registered) {
    await api.post('/devices', { id: device.device_id, name: 'SITRAP PWA' })
    await db.devices.update(accountId, { registered: true })
  }
  return createCommand({ type, entity_id: crypto.randomUUID(), device_id: device.device_id, payload })
}

export async function submitCuyCommand(accountId: string, command: Command) {
  if (['CUY_BIRTH', 'CUY_DEATH'].includes(command.type)) {
    await enqueue(accountId, command)
    if (navigator.onLine) await syncAccount(accountId)
    const entry = await db.events.get(command.event_id)
    if (entry?.status === 'RECHAZADA') throw new Error(entry.error?.message ?? 'Requiere revisión. La intención se conserva.')
    return entry?.status === 'APLICADA' ? 'Aceptada por el servidor.' : 'Guardada localmente; pendiente de aceptación.'
  }
  if (!navigator.onLine) throw new Error('Esta operación requiere conexión.')
  const ack = await api.post<Acknowledgement>('/cuyes/commands', command)
  if (ack.status !== 'APLICADA') throw new ApiError(409, ack.error ?? { code: 'REVIEW', message: 'Requiere revisión.', retryable: false })
  return 'Aceptada por el servidor.'
}

export async function ensureDaySynced(accountId: string, shedId: string, day: string, pens: Pen[], store: SitrapDB = db, sync = syncAccount) {
  if (!navigator.onLine) throw new Error('El cierre definitivo requiere conexión.')
  await sync(accountId)
  const occupations = new Set(pens.filter(p => p.shed_id === shedId).flatMap(p => p.occupations.map(o => o.id)))
  const knownOccupations = new Set(pens.flatMap(p => p.occupations.map(o => o.id)))
  const unresolved = (await listEvents(accountId, store)).filter(e => {
    if (!e.command.type.startsWith('CUY_') || e.command.payload.date !== day || e.status === 'APLICADA' || (e.status === 'RECHAZADA' && e.reviewed_at)) return false
    const ids = e.command.type === 'CUY_BIRTH' ? [e.command.payload.occupation_id] : ((e.command.payload.items ?? []) as { occupation_id: string }[]).map(i => i.occupation_id)
    // Revoked cached pens may no longer exist: block conservatively rather than silently close.
    return ids.some(id => occupations.has(String(id)) || !knownOccupations.has(String(id)))
  })
  if (unresolved.length) throw new Error('Hay novedades pendientes o rechazadas de esta fecha. Revísalas antes de cerrar.')
}
