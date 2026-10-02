import { api } from '../api/client'

it('solo ADMIN puede crear cuentas y asignación global exige rol ADMIN', async () => {
  await api.post('/auth/login', { username: 'produccion', password: 'Demostracion123!' })
  await expect(api.post('/users', { username: 'nuevo', name: 'Nuevo' })).rejects.toMatchObject({ body: { code: 'PERMISSION_DENIED' } })
  await api.post('/auth/logout')
  await api.post('/auth/login', { username: 'admin', password: 'Demostracion123!' })
  const user = await api.post<{ id: string; change_password_required: boolean }>('/users', { username: `new-${crypto.randomUUID()}`, name: 'Reemplazo' })
  expect(user.change_password_required).toBe(true)
  await expect(api.post('/role-assignments', { user_id: user.id, role: 'TRANSPORTE', scope: 'GLOBAL', location_id: null })).rejects.toMatchObject({ body: { code: 'VALIDATION_ERROR' } })
  expect(await api.post('/role-assignments', { user_id: user.id, role: 'TRANSPORTE', scope: 'UBICACION', location_id: 'center-demo' })).toHaveProperty('user_id', user.id)
  await api.post('/auth/logout')
})
