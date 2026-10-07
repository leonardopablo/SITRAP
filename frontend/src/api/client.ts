import { mockFetch } from './mock'
import type { ErrorBody } from './types'

export const apiMode = import.meta.env.VITE_API_MODE === 'mock' ? 'mock' : 'http'
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
    try { response = await transport(`/api/v1${apiMode === 'http' ? backendPath(path) : path}`, {
      ...init, credentials: 'same-origin',
      headers: { Accept: 'application/json', ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...(mutation ? { 'X-CSRFToken': csrf! } : {}), ...init.headers },
    }) } catch { throw new ApiError(0, { code: 'NETWORK_ERROR', message: 'Sin respuesta del servidor. Conserva la intención y reintenta con conexión.', retryable: true }) }
    if (!response.ok) {
      const raw = await response.json().catch(() => null)
      const detail = raw?.error && typeof raw.error === 'object' ? raw.error : raw
      const body: ErrorBody = { code: typeof detail?.code === 'string' ? detail.code : 'HTTP_ERROR', message: typeof detail?.message === 'string' ? detail.message : 'No pudimos completar la solicitud.', field_errors: detail?.field_errors ?? {}, retryable: typeof detail?.retryable === 'boolean' ? detail.retryable : response.status >= 500 }
      if (body.code === 'CSRF_FAILED') csrf = undefined
      if (response.status === 401 && path !== '/auth/login') onExpired()
      throw new ApiError(response.status, body)
    }
    if (response.status === 204) return undefined as T
    const data: unknown = await response.json()
    return (apiMode === 'http' ? adaptResponse(path, data) : data) as T
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
    try { response = await transport(`/api/v1${apiMode === 'http' ? backendPath(path) : path}`, { credentials: 'same-origin', headers: { Accept: 'application/pdf' } }) }
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

export function backendPath(path: string) {
  const [route, query] = path.split('?', 2)
  if (!query) return path
  const params = new URLSearchParams(query)
  if (route.startsWith('/reports/') || route.startsWith('/metrics/')) {
    for (const [from, to] of [['from', 'date_from'], ['to', 'date_to']]) {
      if (params.has(from)) { params.set(to, params.get(from)!); params.delete(from) }
    }
  }
  if (route === '/transfers') { params.delete('status'); params.delete('from'); params.delete('to') }
  return `${route}?${params}`
}

function limaDate(instant: string | null | undefined) {
  if (!instant) return null
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(instant))
  const value = (type: string) => parts.find(part => part.type === type)?.value
  return `${value('year')}-${value('month')}-${value('day')}`
}

// Keep the display model separate from the server's versioned document model.
export function adaptResponse(path: string, value: unknown): unknown {
  if (!value || typeof value !== 'object') return value
  const data = value as Record<string, any>
  if (path === '/auth/me' || path === '/auth/login' || path === '/auth/change-password') return {
    ...data, change_password_required: data.password_change_required,
    assignments: data.assignments?.map((assignment: Record<string, any>) => ({
      ...assignment, location_name: data.locations?.find((location: Record<string, any>) => location.id === assignment.location_id)?.name ?? 'Global',
    })),
  }
  if (path.startsWith('/locations') && Array.isArray(data.results)) return { ...data, results: data.results.map((item: Record<string, any>) => ({ ...item, type: item.kind })) }
  if (path.startsWith('/users') && Array.isArray(data.results)) return { ...data, results: data.results.map((item: Record<string, any>) => ({ ...item, active: item.is_active, change_password_required: item.password_change_required })) }
  if (path.startsWith('/role-assignments') && Array.isArray(data.results)) return { ...data, results: data.results.map((item: Record<string, any>) => ({ ...item, active: !item.ends_at || Date.parse(item.ends_at) > Date.now() })) }
  if (path.startsWith('/transfers')) {
    if (Array.isArray(data.results)) return { ...data, results: data.results.map(adaptTransfer) }
    if (data.current_version) return adaptTransfer(data)
  }
  if (path.startsWith('/milkings')) {
    if (Array.isArray(data.results)) return { ...data, results: data.results.map(adaptMilking) }
    if (data.production_id) return adaptMilking(data)
  }
  if (path.startsWith('/corrections')) {
    if (Array.isArray(data.results)) return { ...data, results: data.results.map(adaptCorrection) }
    if (data.proposed_version) return adaptCorrection(data)
  }
  if (path.startsWith('/metrics/milk')) return {
    ...data, cutoff_at: data.cutoff, time_zone: data.timezone, total_litres: data.liters,
    average_per_registered_day: data.average_per_recorded_day, days_registered: data.recorded_days,
    expected_days: data.days?.length,
    points: data.records?.map((row: Record<string, any>) => ({ ...row, code: data.animals?.find((animal: Record<string, any>) => animal.animal_id === row.animal_id)?.code, litres: row.liters })),
  }
  if (path.startsWith('/metrics/transfers')) return { ...data, cutoff_at: data.cutoff, time_zone: data.timezone,
    days: data.days?.map((day: Record<string, any>) => ({ ...day, picked_litres: day.picked_up_liters, received_litres: day.received_liters,
      transfers: data.records?.filter((record: Record<string, any>) => limaDate(record.pickup_at) === day.date || limaDate(record.reception_at) === day.date).map((record: Record<string, any>) => ({ ...record, id: record.transfer_id, picked_litres: limaDate(record.pickup_at) === day.date ? record.liters : '0', received_litres: limaDate(record.reception_at) === day.date ? record.liters : '0' })) })) }
  return data
}

export function adaptCorrection(item: Record<string, any>) {
  return { ...item, original_quantity: Number(item.original_version?.lines?.[0]?.quantity ?? 0),
    proposed_quantity: Number(item.proposed_version?.lines?.[0]?.quantity ?? 0), proposal_version_id: item.proposed_version?.id,
    approver_transport: item.transport_approver_id, approver_reception: item.reception_approver_id,
    decisions: item.decisions?.map((decision: Record<string, any>) => ({ ...decision, role: decision.function })) }
}

export function adaptMilking(item: Record<string, any>) {
  return { ...item, shift_name: item.turn_id, total_litres: item.quantity,
    linked_litres: null, details: item.details?.map((row: Record<string, any>) => ({ ...row, code: row.animal_id, litres: row.liters })) }
}

export function adaptTransfer(item: Record<string, any>) {
  const line = item.current_version?.lines?.[0]
  return { ...item, units_presentation: Number(line?.units ?? 0),
    origin_name: item.current_version?.origin_id, destination_name: item.current_version?.destination_id,
    driver_name: item.current_version?.driver_id, receiver_name: item.current_version?.receiver_id,
    correction_pending: !!item.pending_correction_id }
}
