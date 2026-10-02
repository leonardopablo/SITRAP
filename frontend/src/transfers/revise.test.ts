import { api } from '../api/client'
import { createCommand } from '../api/commands'
import { getDevice, SitrapDB } from '../offline/db'

it('una versión obsoleta no revisa ni cancela; mock exige motivo', async () => {
  await api.post('/auth/login', { username: 'produccion', password: 'Demostracion123!' })
  const store = new SitrapDB(`revise-${crypto.randomUUID()}`)
  const device = await getDevice('one', store)
  const id = '33333333-3333-4333-8333-333333333333'
  const original = await api.request<{ lock_version: number; version_id: string }>(`/transfers/${id}`)
  const command = createCommand({ type: 'TRANSFER_REVISE', device_id: device.device_id, entity_id: id, expected_version: original.lock_version, payload: { version_id: original.version_id, new_version_id: crypto.randomUUID(), units_presentation: 19, reason: 'Error documental de prueba' } })
  await api.post(`/transfers/${id}/revise`, command)
  await expect(api.post(`/transfers/${id}/revise`, { ...command, event_id: crypto.randomUUID() })).rejects.toMatchObject({ body: { code: 'VERSION_CONFLICT' } })
  expect((await api.request<{ units_presentation: number }>(`/transfers/${id}`)).units_presentation).toBe(19)
  store.close(); await store.delete(); await api.post('/auth/logout')
})
