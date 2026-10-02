import { mockFetch } from './mock'
import type { ErrorBody } from './types'

export const apiMode = import.meta.env.VITE_API_MODE === 'http' ? 'http' : 'mock'
export class ApiError extends Error {
  constructor(public status: number, public body: ErrorBody) { super(body.message) }
}

type Transport = (input: string, init?: RequestInit) => Promise<Response>
export function createApiClient(transport: Transport, onExpired = () => window.dispatchEvent(new Event('sitrap:session-expired'))) {
  let csrf: string | undefined
  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const method = init.method ?? 'GET'
    const mutation = !['GET', 'HEAD'].includes(method)
    if (mutation && !csrf) await refreshCsrf()
    const response = await transport(`/api/v1${path}`, {
      ...init, credentials: 'same-origin',
      headers: { Accept: 'application/json', ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...(mutation ? { 'X-CSRFToken': csrf! } : {}), ...init.headers },
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({ code: 'HTTP_ERROR', message: 'No pudimos completar la solicitud.', retryable: response.status >= 500 })) as ErrorBody
      if (body.code === 'CSRF_FAILED') csrf = undefined
      if (response.status === 401 && path !== '/auth/login') onExpired()
      throw new ApiError(response.status, body)
    }
    if (response.status === 204) return undefined as T
    return response.json() as Promise<T>
  }
  async function refreshCsrf() {
    const response = await transport('/api/v1/auth/csrf', { credentials: 'same-origin' })
    if (!response.ok) throw new ApiError(response.status, { code: 'CSRF_FAILED', message: 'No se pudo preparar el acceso seguro.', retryable: true })
    const body = await response.json() as { csrf_token: string }
    csrf = body.csrf_token
    if (!csrf) throw new Error('Falta csrf_token en el contrato de acceso')
  }
  return { request, refreshCsrf, post: <T>(path: string, body: unknown = {}) => request<T>(path, { method: 'POST', body: JSON.stringify(body) }) }
}
export const api = createApiClient(apiMode === 'mock' ? mockFetch : (input, init) => fetch(input, init))
