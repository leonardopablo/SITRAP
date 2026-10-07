import { createApiClient, ApiError } from '../api/client'
import { mockFetch } from '../api/mock'
import type { Account } from '../api/types'
import { unsubscribeBrowserOnLogout } from '../push/subscription'

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

it('al cerrar sesión no espera indefinidamente a un Service Worker sin controlar la página', async () => {
  const ready = new Promise<ServiceWorkerRegistration>(() => {})
  const getRegistration = vi.fn().mockResolvedValue(undefined)
  const oldWorker = Object.getOwnPropertyDescriptor(navigator, 'serviceWorker')
  const oldPush = Object.getOwnPropertyDescriptor(window, 'PushManager')
  const oldNotification = Object.getOwnPropertyDescriptor(window, 'Notification')
  try {
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: { ready, getRegistration } })
    Object.defineProperty(window, 'PushManager', { configurable: true, value: class {} })
    Object.defineProperty(window, 'Notification', { configurable: true, value: class {} })
    await unsubscribeBrowserOnLogout()
    expect(getRegistration).toHaveBeenCalledOnce()
  } finally {
    if (oldWorker) Object.defineProperty(navigator, 'serviceWorker', oldWorker)
    else Reflect.deleteProperty(navigator, 'serviceWorker')
    if (oldPush) Object.defineProperty(window, 'PushManager', oldPush)
    else Reflect.deleteProperty(window, 'PushManager')
    if (oldNotification) Object.defineProperty(window, 'Notification', oldNotification)
    else Reflect.deleteProperty(window, 'Notification')
  }
})
