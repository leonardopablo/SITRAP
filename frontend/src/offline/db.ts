import Dexie, { type Table } from 'dexie'
import type { Command, ErrorBody } from '../api/types'
import { downloadedOnly, onlineOnly } from '../api/commands'

export type LocalStatus = 'PENDIENTE' | 'ENVIANDO' | 'APLICADA' | 'REQUIERE_SESION' | 'ESPERA_DEPENDENCIA' | 'RECHAZADA'
export interface LocalEvent { event_id: string; account_id: string; device_id: string; command: Command; status: LocalStatus; created_at: string; updated_at: string; error?: ErrorBody; result?: unknown }
export interface AuthorizedCopy { key: string; account_id: string; kind: string; entity_id: string; document: unknown; downloaded_at: string }
export interface DeviceRecord { account_id: string; device_id: string; registered: boolean; prepared_until: string | null }

export class SitrapDB extends Dexie {
  events!: Table<LocalEvent, string>
  copies!: Table<AuthorizedCopy, string>
  devices!: Table<DeviceRecord, string>
  constructor(name = 'sitrap-local-v1') {
    super(name)
    this.version(1).stores({ events: 'event_id, account_id, [account_id+status], created_at', copies: 'key, account_id, [account_id+kind], [account_id+entity_id]', devices: 'account_id' })
  }
}
export const db = new SitrapDB()
const copyKey = (account: string, kind: string, entity: string) => JSON.stringify([account, kind, entity])
export async function getDevice(accountId: string, storage: SitrapDB = db): Promise<DeviceRecord> {
  const existing = await storage.devices.get(accountId)
  if (existing) return existing
  const device = { account_id: accountId, device_id: crypto.randomUUID(), registered: false, prepared_until: null }
  try { await storage.devices.add(device); return device } catch { return (await storage.devices.get(accountId))! }
}
export async function saveCopy(accountId: string, kind: string, entityId: string, document: unknown, storage: SitrapDB = db) {
  await storage.copies.put({ key: copyKey(accountId, kind, entityId), account_id: accountId, kind, entity_id: entityId, document: structuredClone(document), downloaded_at: new Date().toISOString() })
}
export async function readCopy(accountId: string, kind: string, entityId: string, storage: SitrapDB = db) {
  return storage.copies.get(copyKey(accountId, kind, entityId))
}
export async function listEvents(accountId: string, storage: SitrapDB = db) {
  return storage.events.where('account_id').equals(accountId).sortBy('created_at')
}

/** The only offline entry point: durable before reporting local success. */
export async function enqueue(accountId: string, command: Command, storage: SitrapDB = db): Promise<LocalEvent> {
  if (onlineOnly.has(command.type)) throw new Error('Esta acción requiere conexión y estado actual del servidor.')
  if (!accountId || !command.device_id || !command.event_id || !command.entity_id) throw new Error('Falta identidad para guardar la operación.')
  const device = await storage.devices.get(accountId)
  if (device?.device_id !== command.device_id) throw new Error('El dispositivo no corresponde a esta cuenta.')
  if (device.prepared_until && Date.now() >= Date.parse(device.prepared_until)) throw new Error('La preparación offline venció; renueva acceso antes de registrar operaciones.')
  if (downloadedOnly.has(command.type)) {
    const kind = command.type.startsWith('CORRECTION') ? 'correction' : 'transfer'
    const copy = await readCopy(accountId, kind, command.entity_id, storage)
    if (!copy) throw new Error('Descarga primero el documento; sin él solo puedes conservar una nota provisional.')
    if (copy.document && typeof copy.document === 'object' && 'version_id' in copy.document && copy.document.version_id !== command.payload.version_id) throw new Error('La versión visible no coincide con la descargada.')
  }
  const now = new Date().toISOString()
  const entry: LocalEvent = { event_id: command.event_id, account_id: accountId, device_id: command.device_id, command: structuredClone(command), status: 'PENDIENTE', created_at: now, updated_at: now }
  try { await storage.events.add(entry) } catch (error) {
    if (!(error instanceof DOMException && error.name === 'ConstraintError') && !(error instanceof Error && error.name === 'ConstraintError')) throw error
    const previous = await storage.events.get(command.event_id)
    if (!previous || previous.account_id !== accountId || JSON.stringify(previous.command) !== JSON.stringify(entry.command)) throw new Error('El UUID ya pertenece a otra intención.')
    return previous
  }
  return entry
}

export async function pendingCount(accountId: string, storage: SitrapDB = db) {
  const events = await listEvents(accountId, storage)
  return events.filter(event => event.status !== 'APLICADA' && event.status !== 'RECHAZADA').length
}
