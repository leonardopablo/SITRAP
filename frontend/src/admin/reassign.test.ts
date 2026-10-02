import { api } from '../api/client'

it('reasignación solo ADMIN antes de recibir y sin propuesta; no altera cantidad', async () => {
  const id = '55555555-5555-4555-8555-555555555555'
  await api.post('/auth/login', { username: 'produccion', password: 'Demostracion123!' })
  await expect(api.post(`/transfers/${id}/reassign-receiver`, { expected_version: 2, payload: { reason: 'Sustitución', receiver_id: 'nuevo' } })).rejects.toMatchObject({ body: { code: 'PERMISSION_DENIED' } })
  await api.post('/auth/logout')
  await api.post('/auth/login', { username: 'admin', password: 'Demostracion123!' })
  const before = await api.request<{ lock_version: number; units_presentation: number }>(`/transfers/${id}`)
  const command = { event_id: crypto.randomUUID(), device_id: crypto.randomUUID(), expected_version: before.lock_version, payload: { reason: 'Relevo autorizado', receiver_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb' } }
  await api.post(`/transfers/${id}/reassign-receiver`, command)
  expect((await api.request<{ units_presentation: number }>(`/transfers/${id}`)).units_presentation).toBe(before.units_presentation)
  await expect(api.post(`/transfers/${id}/reassign-receiver`, { ...command, event_id: crypto.randomUUID() })).rejects.toMatchObject({ body: { code: 'VERSION_CONFLICT' } })
  await api.post('/auth/logout')
})
