import { afterEach, describe, expect, it, vi } from 'vitest'
import { createCommand } from '../api/commands'
import { enqueue, getDevice, saveCopy, SitrapDB } from '../offline/db'
import { syncAccount } from '../offline/sync'
import { ensureDaySynced } from './actions'
import type { Pen } from './types'

const stores: SitrapDB[] = []
async function setup() {
  const store = new SitrapDB(`cuyes-test-${crypto.randomUUID()}`)
  stores.push(store)
  const account = 'galponero'
  const device = await getDevice(account, store)
  await store.devices.update(account, { registered: true, prepared_until: new Date(Date.now() + 86400000).toISOString() })
  await saveCopy(account, 'cuy_pen', 'pen', { id: 'pen', shed_id: 'shed', occupations: [{ id: 'occ' }] }, store)
  const command = createCommand({ type: 'CUY_DEATH', device_id: device.device_id, entity_id: crypto.randomUUID(), payload: { date: '2026-11-16', reason: 'desconocida', items: [{ occupation_id: 'occ', category: 'MACHO', quality: 'B', quantity: 1 }] } })
  return { store, account, command }
}
afterEach(async () => { await Promise.all(stores.splice(0).map(s => s.delete())); vi.restoreAllMocks() })

describe('Cuyes durable intentions', () => {
  it('preserves UUID and date after lost response, and does not optimistically modify balance', async () => {
    const { store, account, command } = await setup()
    await enqueue(account, command, store)
    await syncAccount(account, async () => { throw new Error('Sin señal') }, store)
    const retry = vi.fn(async commands => [{ event_id: commands[0].event_id, entity_id: commands[0].entity_id, status: 'APLICADA' as const, server_received_at: new Date().toISOString() }])
    await syncAccount(account, retry, store)
    expect(retry.mock.calls[0][0][0]).toEqual(command)
    expect((await store.events.get(command.event_id))?.status).toBe('APLICADA')
    expect((await store.copies.toArray())[0].document).toEqual({ id: 'pen', shed_id: 'shed', occupations: [{ id: 'occ' }] })
  })
  it('retains original intention and error on revoked permissions', async () => {
    const { store, account, command } = await setup()
    await enqueue(account, command, store)
    await syncAccount(account, async () => [{ event_id: command.event_id, entity_id: command.entity_id, status: 'NO_PROCESADA', error: { code: 'PERMISSION_DENIED', message: 'Galpón revocado', retryable: false }, server_received_at: new Date().toISOString() }], store)
    const entry = await store.events.get(command.event_id)
    expect(entry?.status).toBe('RECHAZADA')
    expect(entry?.command).toEqual(command)
    expect(entry?.error?.message).toBe('Galpón revocado')
  })
  it('blocks closing while an intention is pending or rejected', async () => {
    const { store, account, command } = await setup()
    await enqueue(account, command, store)
    const noSend = vi.fn(async () => ({ applied: 0, waiting: 1, rejected: 0 }))
    await expect(ensureDaySynced(account, 'shed', '2026-11-16', [{ shed_id: 'shed', occupations: [{ id: 'occ' }] }] as Pen[], store, noSend)).rejects.toThrow('pendientes')
    await store.events.update(command.event_id, { status: 'RECHAZADA' })
    await expect(ensureDaySynced(account, 'shed', '2026-11-16', [], store, noSend)).rejects.toThrow('pendientes')
    await store.events.update(command.event_id, { reviewed_at: new Date().toISOString(), review_reason: 'Se revisó el hecho rechazado; no aplicado.' })
    await expect(ensureDaySynced(account, 'shed', '2026-11-16', [], store, noSend)).resolves.toBeUndefined()
    await store.events.update(command.event_id, { status: 'APLICADA' })
    await expect(ensureDaySynced(account, 'shed', '2026-11-16', [], store, noSend)).resolves.toBeUndefined()
  })
  it('requires an authorized downloaded occupation and disallows online-only commands', async () => {
    const { store, account, command } = await setup()
    await store.copies.clear()
    await expect(enqueue(account, command, store)).rejects.toThrow('Descarga')
    await expect(enqueue(account, { ...command, type: 'CUY_CLOSE' }, store)).rejects.toThrow('conexión')
  })
})
