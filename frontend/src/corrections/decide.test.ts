import { createCommand } from '../api/commands'
import { enqueue, getDevice, saveCopy, SitrapDB } from '../offline/db'

it('decisión offline conserva versión exacta y no cambia cantidad ni estado físico', async () => {
  const store = new SitrapDB(`decision-${crypto.randomUUID()}`)
  const device = await getDevice('approver', store)
  await store.devices.update('approver', { registered: true, prepared_until: new Date(Date.now() + 86400000).toISOString() })
  const correctionId = crypto.randomUUID(), proposalId = crypto.randomUUID()
  await saveCopy('approver', 'correction', correctionId, { version_id: proposalId, state: 'PENDIENTE', original_quantity: 20, proposed_quantity: 19 }, store)
  const command = createCommand({ type: 'CORRECTION_ACCEPT', device_id: device.device_id, entity_id: correctionId, expected_version: 1, payload: { version_id: proposalId } })
  await enqueue('approver', command, store)
  expect((await store.copies.where('account_id').equals('approver').first())?.document).toMatchObject({ original_quantity: 20, state: 'PENDIENTE' })
  await expect(enqueue('approver', { ...command, event_id: crypto.randomUUID(), payload: { version_id: crypto.randomUUID() } }, store)).rejects.toThrow('versión')
  store.close(); await store.delete()
})
