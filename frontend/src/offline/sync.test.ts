import 'fake-indexeddb/auto'
import { createCommand } from '../api/commands'
import { ApiError } from '../api/client'
import type { Acknowledgement, Command } from '../api/types'
import { enqueue, getDevice, listEvents, SitrapDB } from './db'
import { syncAccount } from './sync'

const setup = async () => { const store = new SitrapDB(`sync-${crypto.randomUUID()}`); const device = await getDevice('one', store); return { store, device } }
const cmd = (device: string, depends_on: string[] = []) => createCommand({ device_id: device, entity_id: crypto.randomUUID(), type: 'MILKING_CREATE', payload: {}, depends_on })
const ack = (command: Command, status: Acknowledgement['status'], error?: Acknowledgement['error']): Acknowledgement => ({ event_id: command.event_id, entity_id: command.entity_id, server_received_at: new Date().toISOString(), status, error })

it('envía padre antes que hijo y conserva UUID al retomar un envío interrumpido', async () => {
  const { store, device } = await setup()
  const parent = cmd(device.device_id)
  const child = cmd(device.device_id, [parent.event_id])
  await enqueue('one', child, store); await enqueue('one', parent, store)
  await store.events.update(parent.event_id, { status: 'ENVIANDO' })
  const sent: string[] = []
  const result = await syncAccount('one', async ([command]) => { sent.push(command.event_id); return [ack(command, 'APLICADA')] }, store)
  expect(sent).toEqual([parent.event_id, child.event_id])
  expect(result.applied).toBe(2)
  expect((await listEvents('one', store)).every(event => event.status === 'APLICADA')).toBe(true)
  store.close(); await store.delete()
})

it('propaga rechazo y no transmite hijo; sesión caducada conserva intención', async () => {
  const { store, device } = await setup()
  const parent = cmd(device.device_id)
  const child = cmd(device.device_id, [parent.event_id])
  await enqueue('one', parent, store); await enqueue('one', child, store)
  const send = vi.fn(async ([command]: Command[]) => [ack(command, 'RECHAZADA', { code: 'VERSION_CONFLICT', message: 'Revisa versión.', retryable: false })])
  expect(await syncAccount('one', send, store)).toEqual({ applied: 0, rejected: 2, waiting: 0 })
  expect(send).toHaveBeenCalledOnce()
  const sessionCommand = cmd(device.device_id)
  await enqueue('one', sessionCommand, store)
  await syncAccount('one', async () => { throw new ApiError(401, { code: 'SESSION_EXPIRED', message: 'Ingresa otra vez.', retryable: false }) }, store)
  expect((await store.events.get(sessionCommand.event_id))?.status).toBe('REQUIERE_SESION')
  store.close(); await store.delete()
})

it('espera un padre ausente en servidor y no afirma éxito sin acuse', async () => {
  const { store, device } = await setup()
  const child = cmd(device.device_id, [crypto.randomUUID()])
  await enqueue('one', child, store)
  const send = vi.fn(async ([command]: Command[]) => [ack(command, 'ESPERA_DEPENDENCIA')])
  expect((await syncAccount('one', send, store)).waiting).toBe(1)
  expect((await store.events.get(child.event_id))?.status).toBe('ESPERA_DEPENDENCIA')
  await syncAccount('one', async () => [], store)
  expect((await store.events.get(child.event_id))?.status).toBe('PENDIENTE')
  store.close(); await store.delete()
})

it('detecta ciclos y nunca inventa versiones esperadas', async () => {
  const { store, device } = await setup()
  const first = cmd(device.device_id)
  const second = cmd(device.device_id, [first.event_id])
  first.depends_on = [second.event_id]
  await enqueue('one', first, store); await enqueue('one', second, store)
  await expect(syncAccount('one', vi.fn(), store)).rejects.toThrow('ciclo')
  store.close(); await store.delete()
})
