import { api } from '../api/client'
import type { Page } from '../api/types'

it('filtra recepción física sin duplicar valor corregido como otra recepción', async () => {
  await api.post('/auth/login', { username: 'recepcion', password: 'Demostracion123!' })
  const date = new Date().toISOString().slice(0, 10)
  const page = await api.request<Page<{ id: string; units_presentation: number; original_quantity: number }>>(`/transfers?status=RECIBIDO&from=${date}&to=${date}`)
  expect(page.results).toHaveLength(1)
  expect(page.results[0].units_presentation).toBe(18)
  expect(page.results[0].original_quantity).toBe(20)
  await api.post('/auth/logout')
})
