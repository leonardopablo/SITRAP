import { createCommand } from '../api/commands'
import { enqueue, getDevice, SitrapDB } from '../offline/db'

it('el envío queda dependiente del borrador y no se crea una confirmación remota', async () => {
  const store = new SitrapDB(`send-${crypto.randomUUID()}`)
  const device = await getDevice('producer', store)
  await store.devices.update('producer', { registered: true, prepared_until: new Date(Date.now() + 86400000).toISOString() })
  const id = crypto.randomUUID(), version = crypto.randomUUID()
  const draft = createCommand({ type: 'TRANSFER_CREATE', entity_id: id, device_id: device.device_id, payload: { version_id: version } })
  await enqueue('producer', draft, store)
  const send = createCommand({ type: 'TRANSFER_SEND', entity_id: id, device_id: device.device_id, expected_version: 1, depends_on: [draft.event_id], payload: { version_id: version } })
  await enqueue('producer', send, store)
  expect((await store.events.get(send.event_id))?.command.depends_on).toEqual([draft.event_id])
  expect((await store.events.get(send.event_id))?.status).toBe('PENDIENTE')
  store.close(); await store.delete()
})
