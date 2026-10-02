import { createApiClient, ApiError } from '../api/client'
import { mockFetch } from '../api/mock'
import type { Account } from '../api/types'

it('obtiene CSRF antes de login y usa cookies de mismo origen', async () => {
  const transport = vi.fn(mockFetch)
  const client = createApiClient(transport, vi.fn())
  await client.post('/auth/login', { username: 'produccion', password: 'Temporal123!' })
  expect(transport.mock.calls[0][0]).toBe('/api/v1/auth/csrf')
  expect(transport.mock.calls[1][1]).toMatchObject({ credentials: 'same-origin', headers: { 'X-CSRFToken': 'demo-csrf' } })
  expect((await client.request<Account>('/auth/me')).change_password_required).toBe(true)
  await client.post('/auth/change-password', { current_password: 'Temporal123!', new_password: 'NuevaClave12345!' })
  expect((await client.request<Account>('/auth/me')).change_password_required).toBe(false)
  await client.post('/auth/logout')
})

it('distingue credenciales inválidas y expiración; nunca conserva contraseña', async () => {
  const expired = vi.fn()
  const client = createApiClient(mockFetch, expired)
  await expect(client.post('/auth/login', { username: 'produccion', password: 'incorrecta' })).rejects.toBeInstanceOf(ApiError)
  expect(expired).not.toHaveBeenCalled()
  await expect(client.request('/auth/me')).rejects.toMatchObject({ body: { code: 'SESSION_EXPIRED' } })
  expect(expired).toHaveBeenCalledOnce()
  expect(localStorage.length).toBe(0)
})
