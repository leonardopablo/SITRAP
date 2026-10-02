import { createCommand } from '../api/commands'
import { enqueue, getDevice, saveCopy, SitrapDB } from '../offline/db'

it('recogida usa versión descargada y no permite cantidad libre', async () => {
  const store = new SitrapDB(`pickup-${crypto.randomUUID()}`)
  const device = await getDevice('transporte', store)
  await store.devices.update('transporte', { registered: true, prepared_until: new Date(Date.now() + 86400000).toISOString() })
  const id = crypto.randomUUID(), version = crypto.randomUUID()
  await saveCopy('transporte', 'transfer', id, { version_id: version, units_presentation: 20 }, store)
  const command = createCommand({ type: 'TRANSFER_PICKUP', device_id: device.device_id, entity_id: id, expected_version: 4, payload: { version_id: version } })
  expect((await enqueue('transporte', command, store)).command.payload).toEqual({ version_id: version })
  await expect(enqueue('transporte', { ...command, event_id: crypto.randomUUID(), payload: { version_id: crypto.randomUUID() } }, store)).rejects.toThrow('versión')
  store.close(); await store.delete()
})
