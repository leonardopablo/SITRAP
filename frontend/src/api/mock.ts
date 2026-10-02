import type { Account, Role } from './types'
import type { Notification } from '../notifications/types'
import type { Animal } from '../animals/types'

const roles: Role[] = ['PRODUCCION', 'TRANSPORTE', 'RECEPCION', 'ADMIN']
export const demoAccounts: Account[] = roles.map((role, index) => ({
  id: `00000000-0000-4000-8000-00000000000${index + 1}`,
  username: role.toLowerCase(), name: `Cuenta demo ${role.toLowerCase()}`,
  change_password_required: false,
  assignments: [{ id: `assignment-${index}`, role, scope: role === 'ADMIN' ? 'GLOBAL' : 'UBICACION', location_id: role === 'ADMIN' ? null : role === 'RECEPCION' ? 'destination-demo' : 'center-demo', location_name: role === 'ADMIN' ? 'Todos los centros' : role === 'RECEPCION' ? 'Punto de venta demo' : 'Centro demo' }],
  capabilities: role === 'ADMIN' ? ['admin:read', 'accounts:manage', 'catalog:manage'] : [`${role.toLowerCase()}:operate`],
}))
let session: Account | null = null
let expiresAt = 0
const notifications = new Map<string, Notification[]>()
const animals: Animal[] = []
export function seedDemoNotifications(accountId: string, items: Notification[]) { notifications.set(accountId, structuredClone(items)) }
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const error = (code: string, message: string, status: number) => json({ code, message, field_errors: {}, retryable: false }, status)

/** Simulation only: no server persistence, security or cross-device integration. */
export async function mockFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const path = input.replace('/api/v1', '').split('?')[0]
  const method = init.method ?? 'GET'
  if (path === '/auth/csrf') return json({ csrf_token: 'demo-csrf' })
  if (method !== 'GET' && new Headers(init.headers).get('X-CSRFToken') !== 'demo-csrf') return error('CSRF_FAILED', 'Renueva el acceso seguro.', 403)
  const data = typeof init.body === 'string' ? JSON.parse(init.body) : {}
  if (path === '/auth/login') {
    const found = demoAccounts.find(account => account.username === data.username)
    if (!found || !['Demostracion123!', 'Temporal123!'].includes(data.password)) return error('INVALID_CREDENTIALS', 'Usuario o contraseña incorrectos.', 401)
    session = { ...found, change_password_required: data.password === 'Temporal123!' }
    expiresAt = Date.now() + 12 * 60 * 60 * 1000
    return json({ authenticated: true })
  }
  if (!session || Date.now() >= expiresAt) return error('SESSION_EXPIRED', 'Tu sesión venció. Ingresa con la misma cuenta para continuar.', 401)
  if (path === '/auth/me') return json(session)
  if (path === '/auth/logout') { session = null; return new Response(null, { status: 204 }) }
  if (path === '/auth/change-password') {
    if (!['Demostracion123!', 'Temporal123!'].includes(data.current_password)) return error('VALIDATION_ERROR', 'La contraseña actual no coincide.', 422)
    if (typeof data.new_password !== 'string' || data.new_password.length < 12) return error('VALIDATION_ERROR', 'Usa al menos 12 caracteres.', 422)
    session = { ...session, change_password_required: false }
    return json({ changed: true })
  }
  if (path === '/notifications' && method === 'GET') {
    const items = notifications.get(session.id) ?? []
    return json({ results: items, next: null, count: items.length, unread_count: items.filter(item => !item.read_at).length })
  }
  if (path.startsWith('/notifications/') && path.endsWith('/read') && method === 'POST') {
    const id = path.split('/')[2]
    const found = notifications.get(session.id)?.find(item => item.id === id)
    if (!found) return error('PERMISSION_DENIED', 'Aviso no disponible para esta cuenta.', 403)
    found.read_at ??= new Date().toISOString()
    return json(found)
  }
  if (path === '/animals' && method === 'GET') {
    if (session.assignments[0].role === 'TRANSPORTE' || session.assignments[0].role === 'RECEPCION') return error('PERMISSION_DENIED', 'Sin permiso para consultar vacas.', 403)
    const items = animals.filter(item => session!.assignments[0].scope === 'GLOBAL' || item.center_id === session!.assignments[0].location_id)
    return json({ results: items, next: null, count: items.length })
  }
  if (path === '/animals' && method === 'POST') {
    if (!['ADMIN', 'PRODUCCION'].includes(session.assignments[0].role)) return error('PERMISSION_DENIED', 'Sin permiso para registrar vacas.', 403)
    if (animals.some(item => item.code.toLowerCase() === String(data.code).toLowerCase())) return error('VALIDATION_ERROR', 'El código ya existe.', 422)
    if (session.assignments[0].scope !== 'GLOBAL' && session.assignments[0].location_id !== data.center_id) return error('PERMISSION_DENIED', 'Centro fuera de tu ámbito.', 403)
    const animal: Animal = { id: crypto.randomUUID(), code: data.code, name: data.name || null, sex: 'HEMBRA', species_id: data.species_id, status: 'ACTIVO', center_id: data.center_id, center_name: 'Centro demo' }
    animals.push(animal); return json(animal, 201)
  }
  if (path.startsWith('/animals/') && method === 'GET') {
    const item = animals.find(animal => animal.id === path.split('/')[2])
    if (!item || !['ADMIN', 'PRODUCCION'].includes(session.assignments[0].role) || (session.assignments[0].scope !== 'GLOBAL' && session.assignments[0].location_id !== item.center_id)) return error('PERMISSION_DENIED', 'Vaca fuera de tu ámbito.', 403)
    return json(item)
  }
  if (path.startsWith('/animals/') && method === 'PATCH') {
    const item = animals.find(animal => animal.id === path.split('/')[2])
    if (!item || !['ADMIN', 'PRODUCCION'].includes(session.assignments[0].role) || (session.assignments[0].scope !== 'GLOBAL' && session.assignments[0].location_id !== item.center_id)) return error('PERMISSION_DENIED', 'Sin permiso para editar esta vaca.', 403)
    if (animals.some(animal => animal.id !== item.id && animal.code.toLowerCase() === String(data.code).toLowerCase())) return error('VALIDATION_ERROR', 'El código ya existe.', 422)
    item.code = data.code; item.name = data.name || null; item.status = data.status
    return json(item)
  }
  if (path === '/devices' && method === 'POST') return json({ device_id: data.device_id, prepared_until: new Date(Date.now() + 7 * 86400000).toISOString() })
  if (path === '/sync/bootstrap') return json({ cursor: 'demo-1', prepared_until: new Date(Date.now() + 7 * 86400000).toISOString(), copies: [], tombstones: [] })
  if (path === '/sync/changes') return json({ cursor: 'demo-1', copies: [], tombstones: [] })
  return error('MOCK_NOT_IMPLEMENTED', 'Este punto del contrato aún no está implementado en la simulación.', 501)
}
