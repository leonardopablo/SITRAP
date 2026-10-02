import { api } from '../api/client'
import { createCommand } from '../api/commands'

it('retiro conserva cantidad original y no recicla decisiones', async () => {
  await api.post('/auth/login', { username: 'produccion', password: 'Demostracion123!' })
  const id = '55555555-5555-4555-8555-555555555555'
  const transfer = await api.request<{ lock_version: number; units_presentation: number }>(`/transfers/${id}`)
  const device = crypto.randomUUID()
  const create = createCommand({ type: 'CORRECTION_CREATE', entity_id: id, device_id: device, expected_version: transfer.lock_version, payload: { correction_id: crypto.randomUUID(), proposal_version_id: crypto.randomUUID(), new_quantity: 12, reason: 'Error documental' } })
  const result = await api.post<{ result: { id: string; lock_version: number } }>(`/transfers/${id}/corrections`, create)
  const withdraw = createCommand({ type: 'CORRECTION_WITHDRAW', entity_id: result.result.id, device_id: device, expected_version: result.result.lock_version, payload: { reason: 'Retiro de prueba' } })
  await api.post(`/corrections/${result.result.id}/withdraw`, withdraw)
  expect((await api.request<{ units_presentation: number; correction_pending: boolean }>(`/transfers/${id}`))).toMatchObject({ units_presentation: transfer.units_presentation, correction_pending: false })
  await expect(api.post(`/corrections/${result.result.id}/withdraw`, { ...withdraw, event_id: crypto.randomUUID() })).rejects.toMatchObject({ body: { code: 'VERSION_CONFLICT' } })
  await api.post('/auth/logout')
})
