import { api } from '../api/client'

it('no incluye stock; ADMIN habilita producto y evita duplicado', async () => {
  await api.post('/auth/login', { username: 'admin', password: 'Demostracion123!' })
  const id = crypto.randomUUID()
  const product = await api.post<{ id: string }>('/products', { code: `P-${id}`, name: 'Producto de prueba', active: true })
  const assignment = await api.post<{ id: string }>('/center-products', { center_id: 'center-demo', product_id: product.id, enabled: true })
  expect(assignment.id).toBeTruthy()
  await expect(api.post('/center-products', { center_id: 'center-demo', product_id: product.id, enabled: true })).rejects.toMatchObject({ body: { code: 'VALIDATION_ERROR' } })
  await expect(api.patch(`/products/${product.id}`, { stock: 100 })).rejects.toMatchObject({ body: { code: 'VALIDATION_ERROR' } })
  await api.post('/auth/logout')
})
