import { api } from '../api/client'
import { createCommand } from '../api/commands'

it('rectificación del ordeño no cambia entregas aceptadas; versión obsoleta rechazada', async () => {
  await api.post('/auth/login', { username: 'produccion', password: 'Demostracion123!' })
  const id = '99999999-9999-4999-8999-999999999999'
  const before = await api.request<{ lock_version: number; total_litres: string; details: { animal_id: string; code: string; litres: string }[] }>(`/milkings/${id}`)
  const command = createCommand({ type: 'MILKING_RECTIFY', device_id: crypto.randomUUID(), entity_id: id, expected_version: before.lock_version, payload: { reason: 'Ajuste documental', new_version_id: crypto.randomUUID(), details: before.details.map(item => ({ ...item, litres: item.animal_id === 'demo-vaca-b' ? '9.000' : item.litres })) } })
  await api.post(`/milkings/${id}/rectify`, command)
  expect((await api.request<{ total_litres: string }>(`/milkings/${id}`)).total_litres).toBe('9.000')
  await expect(api.post(`/milkings/${id}/void`, { ...command, event_id: crypto.randomUUID(), payload: { reason: 'Anular' } })).rejects.toMatchObject({ body: { code: 'VERSION_CONFLICT' } })
  await api.post('/auth/logout')
})
