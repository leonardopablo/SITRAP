import { api, apiMode } from '../api/client'
import { db, getDevice, saveCopy, type SitrapDB } from './db'

/** Provisional DTO until B28 publishes OpenAPI. Always scoped to authenticated account. */
interface Snapshot { cursor: string; prepared_until?: string; copies: { kind: string; entity_id: string; document: unknown }[]; tombstones: { kind: string; entity_id: string }[] }
function copyKey(account: string, kind: string, entity: string) { return JSON.stringify([account, kind, entity]) }
export async function prepareAccount(accountId: string, store: SitrapDB = db) {
  if (!navigator.onLine) throw new Error('Necesitas conexión para preparar el dispositivo.')
  const device = await getDevice(accountId, store)
  const registered = await api.post<{ device_id: string; prepared_until?: string }>('/devices', { device_id: device.device_id })
  if (registered.device_id !== device.device_id) throw new Error('El servidor devolvió otro dispositivo.')
  const snapshot = await api.request<Snapshot>('/sync/bootstrap')
  if (!Array.isArray(snapshot.copies) || !Array.isArray(snapshot.tombstones) || typeof snapshot.cursor !== 'string') throw new Error('Preparación incompleta. No se actualizó el dispositivo.')
  await store.transaction('rw', store.devices, store.copies, async () => {
    await store.copies.where('account_id').equals(accountId).delete()
    for (const item of snapshot.copies) await saveCopy(accountId, item.kind, item.entity_id, item.document, store)
    const preparedUntil = snapshot.prepared_until ?? registered.prepared_until ?? null
    await store.devices.put({ ...device, registered: true, prepared_until: preparedUntil, cursor: snapshot.cursor })
  })
  return snapshot.copies.length
}
export async function applyChanges(accountId: string, store: SitrapDB = db) {
  if (!navigator.onLine) return 0
  const device = await getDevice(accountId, store)
  if (!device.registered || !device.cursor) throw new Error('Prepara el dispositivo antes de actualizar datos.')
  const snapshot = await api.request<Snapshot>(`/sync/changes?cursor=${encodeURIComponent(device.cursor)}`)
  if (!Array.isArray(snapshot.copies) || !Array.isArray(snapshot.tombstones) || typeof snapshot.cursor !== 'string') throw new Error('Cambios incompletos; renueva la preparación.')
  await store.transaction('rw', store.devices, store.copies, async () => {
    for (const item of snapshot.tombstones) await store.copies.delete(copyKey(accountId, item.kind, item.entity_id))
    for (const item of snapshot.copies) await saveCopy(accountId, item.kind, item.entity_id, item.document, store)
    await store.devices.update(accountId, { cursor: snapshot.cursor })
  })
  return snapshot.copies.length + snapshot.tombstones.length
}
export function canSyncRemotely() { return apiMode === 'http' }
