import { api } from '../api/client'
import { createCommand } from '../api/commands'
import { getDevice, SitrapDB } from '../offline/db'

it('proponer no cambia cantidad vigente; bloquea nueva propuesta y recepción pendiente', async () => {
  await api.post('/auth/login', { username: 'produccion', password: 'Demostracion123!' })
  const store = new SitrapDB(`correction-${crypto.randomUUID()}`)
  const device = await getDevice('one', store)
  const id = '55555555-5555-4555-8555-555555555555'
  const transfer = await api.request<{ lock_version: number; units_presentation: number }>(`/transfers/${id}`)
  const command = createCommand({ type: 'CORRECTION_CREATE', device_id: device.device_id, entity_id: id, expected_version: transfer.lock_version, payload: { correction_id: crypto.randomUUID(), proposal_version_id: crypto.randomUUID(), new_quantity: 14, reason: 'Error de transcripción' } })
  await api.post(`/transfers/${id}/corrections`, command)
  const after = await api.request<{ units_presentation: number; correction_pending: boolean }>(`/transfers/${id}`)
  expect(after.units_presentation).toBe(transfer.units_presentation)
  expect(after.correction_pending).toBe(true)
  await expect(api.post(`/transfers/${id}/corrections`, { ...command, event_id: crypto.randomUUID(), expected_version: transfer.lock_version + 1 })).rejects.toMatchObject({ body: { code: 'CORRECTION_PENDING' } })
  store.close(); await store.delete(); await api.post('/auth/logout')
})
