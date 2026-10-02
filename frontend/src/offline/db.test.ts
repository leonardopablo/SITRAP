import 'fake-indexeddb/auto'
import { createCommand } from '../api/commands'
import { enqueue, getDevice, listEvents, pendingCount, saveCopy, SitrapDB } from './db'

const commandFor = (device: string, type: 'MILKING_CREATE' | 'TRANSFER_PICKUP' = 'MILKING_CREATE') => createCommand({ type, entity_id: crypto.randomUUID(), device_id: device, payload: { version_id: crypto.randomUUID() } })

it('conserva UUID y pendientes tras cerrar y abrir IndexedDB; no mezcla cuentas', async () => {
  const name = `test-${crypto.randomUUID()}`
  const storage = new SitrapDB(name)
  const one = await getDevice('one', storage)
  const original = commandFor(one.device_id)
  await enqueue('one', original, storage)
  storage.close()
  const reopened = new SitrapDB(name)
  expect((await listEvents('one', reopened))[0].command).toEqual(original)
  expect(await pendingCount('one', reopened)).toBe(1)
  expect(await pendingCount('two', reopened)).toBe(0)
  await expect(enqueue('two', original, reopened)).rejects.toThrow('dispositivo')
  const duplicate = await enqueue('one', original, reopened)
  expect(duplicate.event_id).toBe(original.event_id)
  expect((await listEvents('one', reopened))).toHaveLength(1)
  reopened.close(); await reopened.delete()
})

it('rechaza confirmaciones no descargadas, versiones ajenas y comandos solo online', async () => {
  const storage = new SitrapDB(`test-${crypto.randomUUID()}`)
  const device = await getDevice('one', storage)
  const pickup = commandFor(device.device_id, 'TRANSFER_PICKUP')
  await expect(enqueue('one', pickup, storage)).rejects.toThrow('Descarga')
  await saveCopy('one', 'transfer', pickup.entity_id, { version_id: 'old' }, storage)
  await expect(enqueue('one', pickup, storage)).rejects.toThrow('versión')
  await saveCopy('one', 'transfer', pickup.entity_id, { version_id: pickup.payload.version_id }, storage)
  expect((await enqueue('one', pickup, storage)).status).toBe('PENDIENTE')
  await expect(enqueue('one', { ...pickup, event_id: crypto.randomUUID(), type: 'TRANSFER_CANCEL' }, storage)).rejects.toThrow('conexión')
  storage.close(); await storage.delete()
})

it('no altera silenciosamente una intención ya registrada y bloquea preparación vencida', async () => {
  const storage = new SitrapDB(`test-${crypto.randomUUID()}`)
  const device = await getDevice('one', storage)
  const command = commandFor(device.device_id)
  await enqueue('one', command, storage)
  await expect(enqueue('one', { ...command, payload: { litros: '999' } }, storage)).rejects.toThrow('UUID')
  await storage.devices.update('one', { prepared_until: new Date(0).toISOString() })
  await expect(enqueue('one', commandFor(device.device_id), storage)).rejects.toThrow('venció')
  storage.close(); await storage.delete()
})
