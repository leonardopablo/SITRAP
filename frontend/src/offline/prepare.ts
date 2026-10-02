import { api, apiMode, adaptTransfer } from '../api/client'
import { db, getDevice, saveCopy, type SitrapDB } from './db'

interface Snapshot { cursor: string | null; next_page: string | null; preparation_expires_at: string | null; results: { entity_type: string; id: string; deleted: boolean; data: unknown }[] }
function copyKey(account: string, kind: string, entity: string) { return JSON.stringify([account, kind, entity]) }
async function snapshotPages(path: string, deviceId: string): Promise<{ cursor: string; preparedUntil: string | null; entries: Snapshot['results'] }> {
  const entries: Snapshot['results'] = []
  let page: string | null = null
  const seen = new Set<string>()
  while (true) {
    const query: string = page ? `&page=${encodeURIComponent(page)}` : ''
    const result: Snapshot = await api.request<Snapshot>(`${path}${path.includes('?') ? '&' : '?'}limit=200${query}`, { headers: { 'X-Device-ID': deviceId } })
    if (!Array.isArray(result.results)) throw new Error('Página de preparación incompleta.')
    entries.push(...result.results)
    if (!result.next_page) {
      if (!result.cursor) throw new Error('No se recibió cursor completo.')
      return { cursor: result.cursor, preparedUntil: result.preparation_expires_at, entries }
    }
    if (seen.has(result.next_page)) throw new Error('Paginación repetida; conserva las copias anteriores.')
    seen.add(result.next_page)
    page = result.next_page
  }
}
export async function prepareAccount(accountId: string, store: SitrapDB = db) {
  if (!navigator.onLine) throw new Error('Necesitas conexión para preparar el dispositivo.')
  const device = await getDevice(accountId, store)
  if (apiMode === 'mock') {
    const registered = await api.post<{ device_id: string; prepared_until?: string }>('/devices', { device_id: device.device_id })
    if (registered.device_id !== device.device_id) throw new Error('El servidor devolvió otro dispositivo.')
    const snapshot = await api.request<{ cursor: string; prepared_until?: string; copies: { kind: string; entity_id: string; document: unknown }[] }>('/sync/bootstrap')
    await store.transaction('rw', store.devices, store.copies, async () => {
      await store.copies.where('account_id').equals(accountId).delete()
      for (const item of snapshot.copies) await saveCopy(accountId, item.kind, item.entity_id, item.document, store)
      await store.devices.put({ ...device, registered: true, prepared_until: snapshot.prepared_until ?? registered.prepared_until ?? null, cursor: snapshot.cursor })
    })
    return snapshot.copies.length
  }
  const registered = await api.post<{ id: string }>('/devices', { id: device.device_id, name: 'SITRAP PWA' })
  if (registered.id !== device.device_id) throw new Error('El servidor devolvió otro dispositivo.')
  const snapshot = await snapshotPages('/sync/bootstrap', device.device_id)
  await store.transaction('rw', store.devices, store.copies, async () => {
    await store.copies.where('account_id').equals(accountId).delete()
    for (const item of snapshot.entries) if (!item.deleted) await saveCopy(accountId, item.entity_type, item.id, item.entity_type === 'transfer' ? adaptTransfer(item.data as Record<string, unknown>) : item.data, store)
    await store.devices.put({ ...device, registered: true, prepared_until: snapshot.preparedUntil, cursor: snapshot.cursor })
  })
  return snapshot.entries.length
}
export async function applyChanges(accountId: string, store: SitrapDB = db) {
  if (!navigator.onLine) return 0
  const device = await getDevice(accountId, store)
  if (!device.registered || !device.cursor) throw new Error('Prepara el dispositivo antes de actualizar datos.')
  if (apiMode === 'mock') {
    const snapshot = await api.request<{ cursor: string; copies: { kind: string; entity_id: string; document: unknown }[]; tombstones: { kind: string; entity_id: string }[] }>(`/sync/changes?cursor=${encodeURIComponent(device.cursor)}`)
    await store.transaction('rw', store.devices, store.copies, async () => {
      for (const item of snapshot.tombstones) await store.copies.delete(copyKey(accountId, item.kind, item.entity_id))
      for (const item of snapshot.copies) await saveCopy(accountId, item.kind, item.entity_id, item.document, store)
      await store.devices.update(accountId, { cursor: snapshot.cursor })
    })
    return snapshot.copies.length + snapshot.tombstones.length
  }
  const snapshot = await snapshotPages(`/sync/changes?cursor=${encodeURIComponent(device.cursor)}`, device.device_id)
  await store.transaction('rw', store.devices, store.copies, async () => {
    for (const item of snapshot.entries) {
      if (item.deleted) await store.copies.delete(copyKey(accountId, item.entity_type, item.id))
      else await saveCopy(accountId, item.entity_type, item.id, item.entity_type === 'transfer' ? adaptTransfer(item.data as Record<string, unknown>) : item.data, store)
    }
    await store.devices.update(accountId, { cursor: snapshot.cursor, prepared_until: snapshot.preparedUntil })
  })
  return snapshot.entries.length
}
export function canSyncRemotely() { return apiMode === 'http' }
