import { api, ApiError } from '../api/client'
import { createCommand } from '../api/commands'
import type { Acknowledgement, Command } from '../api/types'
import { db, getDevice } from '../offline/db'
import type { Candidate, Sale, Selection, SaleType } from './salesTypes'

export async function commercialCommand(account: string, type: SaleType, entityId: string, payload: Record<string, unknown>, version?: number) {
  if (!navigator.onLine) throw new Error('Las operaciones de venta requieren conexión.')
  const device = await getDevice(account)
  if (!device.registered) {
    await api.post('/devices', { id: device.device_id, name: 'SITRAP PWA' })
    await db.devices.update(account, { registered: true })
  }
  return createCommand({ type, entity_id: entityId, device_id: device.device_id, payload, ...(version ? { expected_version: version } : {}) })
}

export async function sendCommercial(command: Command) {
  if (!navigator.onLine) throw new Error('Conéctate para confirmar la operación.')
  const ack = await api.post<Acknowledgement>('/cuyes/sales/commands', command)
  if (ack.status !== 'APLICADA') throw new ApiError(409, ack.error ?? { code: 'REVIEW', message: 'La operación requiere revisión.', retryable: false })
  return ack
}

/** Stable FIFO: backend supplies sorted, authorized buckets; claims are consumed locally per suggestion. */
export function suggestFifo(order: Sale, candidates: Candidate[]): Selection[] {
  const result: Selection[] = []
  const left = new Map(candidates.map(c => [`${c.occupation_id}:${c.category}:${c.quality}`, c.available]))
  for (const line of order.lines) {
    for (const component of line.recipe) {
      let needed = line.units * component.quantity
      for (const other of order.preparation?.other_allocations ?? []) {
        if (other.line_id === line.id && other.category === component.category && other.quality === component.quality) needed -= other.quantity
      }
      for (const c of candidates) {
        if (needed <= 0) break
        if (c.category !== component.category || c.quality !== component.quality) continue
        const key = `${c.occupation_id}:${c.category}:${c.quality}`
        const quantity = Math.min(needed, left.get(key) ?? 0)
        if (quantity > 0) {
          result.push({ line_id: line.id, occupation_id: c.occupation_id, category: c.category, quality: c.quality, quantity, pen: c.pen, shed_id: c.shed_id })
          left.set(key, left.get(key)! - quantity); needed -= quantity
        }
      }
      if (needed > 0) throw new Error('No alcanza la selección autorizada. Coordina con los otros galpones; no se sustituye ningún componente.')
    }
  }
  return result
}
