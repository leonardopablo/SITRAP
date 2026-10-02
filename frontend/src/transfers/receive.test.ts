import { createCommand } from '../api/commands'
import { enqueue, getDevice, saveCopy, SitrapDB } from '../offline/db'

it('la recepción solo guarda versión descargada, sin litros editables', async () => {
  const store = new SitrapDB(`receive-${crypto.randomUUID()}`)
  const device = await getDevice('receptor', store)
  await store.devices.update('receptor', { registered: true, prepared_until: new Date(Date.now() + 86400000).toISOString() })
  const id = crypto.randomUUID(), version = crypto.randomUUID()
  const command = createCommand({ type: 'TRANSFER_RECEIVE', device_id: device.device_id, entity_id: id, expected_version: 2, payload: { version_id: version } })
  await expect(enqueue('receptor', command, store)).rejects.toThrow('Descarga')
  await saveCopy('receptor', 'transfer', id, { version_id: version, correction_pending: false }, store)
  expect((await enqueue('receptor', command, store)).command.payload).toEqual({ version_id: version })
  store.close(); await store.delete()
})
