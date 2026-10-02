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
    if (!path.startsWith('/') || path.startsWith('//') || path.includes('://')) throw new Error('La ruta API debe ser interna')
    let response: Response
    try { response = await transport(`/api/v1${path}`, {
      ...init, credentials: 'same-origin',
      headers: { Accept: 'application/json', ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...(mutation ? { 'X-CSRFToken': csrf! } : {}), ...init.headers },
    }) } catch { throw new ApiError(0, { code: 'NETWORK_ERROR', message: 'Sin respuesta del servidor. Conserva la intención y reintenta con conexión.', retryable: true }) }
    if (!response.ok) {
      const raw = await response.json().catch(() => null)
      const body: ErrorBody = { code: typeof raw?.code === 'string' ? raw.code : 'HTTP_ERROR', message: typeof raw?.message === 'string' ? raw.message : 'No pudimos completar la solicitud.', field_errors: raw?.field_errors ?? {}, retryable: typeof raw?.retryable === 'boolean' ? raw.retryable : response.status >= 500 }
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
  async function pdf(path: string): Promise<Blob> {
    if (!path.startsWith('/reports/') || !path.includes('.pdf') || path.startsWith('//')) throw new Error('Informe no autorizado por este cliente.')
    let response: Response
    try { response = await transport(`/api/v1${path}`, { credentials: 'same-origin', headers: { Accept: 'application/pdf' } }) }
    catch { throw new ApiError(0, { code: 'NETWORK_ERROR', message: 'Conéctate para descargar el PDF.', retryable: true }) }
    if (!response.ok) {
      const raw = await response.json().catch(() => null)
      if (response.status === 401) onExpired()
      throw new ApiError(response.status, { code: raw?.code ?? 'REPORT_ERROR', message: raw?.message ?? 'No se pudo generar el PDF.', retryable: response.status >= 500 })
    }
    if (!response.headers.get('Content-Type')?.toLowerCase().includes('application/pdf')) throw new Error('El servidor no devolvió un PDF. No se descargó un informe incompleto.')
    return response.blob()
  }
  return { request, refreshCsrf, pdf, post: <T>(path: string, body: unknown = {}) => request<T>(path, { method: 'POST', body: JSON.stringify(body) }), patch: <T>(path: string, body: unknown) => request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }) }
}
export const api = createApiClient(apiMode === 'mock' ? mockFetch : (input, init) => fetch(input, init))
