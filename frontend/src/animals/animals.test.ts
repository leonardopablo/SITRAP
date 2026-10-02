import { api } from '../api/client'
import type { Animal } from './types'
import type { Page } from '../api/types'

it('valida permiso de rol y de centro en el adaptador simulado', async () => {
  await api.post('/auth/login', { username: 'transporte', password: 'Demostracion123!' })
  await expect(api.request('/animals')).rejects.toMatchObject({ body: { code: 'PERMISSION_DENIED' } })
  await api.post('/auth/logout')
  await api.post('/auth/login', { username: 'produccion', password: 'Demostracion123!' })
  await expect(api.post('/animals', { code: 'V-TEST', center_id: 'otro-centro', species_id: 'bovina-demo' })).rejects.toMatchObject({ body: { code: 'PERMISSION_DENIED' } })
  const animal = await api.post<Animal>('/animals', { code: `V-${crypto.randomUUID()}`, name: '', center_id: 'center-demo', species_id: 'bovina-demo' })
  expect(animal.name).toBeNull()
  expect((await api.request<Page<Animal>>('/animals')).results).toContainEqual(animal)
  await api.post('/auth/logout')
})
