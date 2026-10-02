import type { Account, Role } from './types'
import type { Notification } from '../notifications/types'
import type { Animal } from '../animals/types'
import type { AssignmentOptions, Lot, Presentation } from '../transfers/types'

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
const demoLots: Lot[] = [{ id: '11111111-1111-4111-8111-111111111111', code: 'DEMO-LOTE-01', center_id: 'center-demo', product_id: 'milk-demo', produced_litres: '23.500', unlinked_litres: '23.500', confirmed: true }]
const demoPresentation: Presentation = { id: '22222222-2222-4222-8222-222222222222', product_id: 'milk-demo', name: 'Bolsa de 1 L', content_base: '1.000', admits_fraction: false, active: true }
const demoOptions: AssignmentOptions = { destinations: [{ id: 'destination-demo', name: 'Punto de venta demo' }], drivers: [{ id: demoAccounts[1].id, name: demoAccounts[1].name }], receivers: [{ id: demoAccounts[2].id, name: demoAccounts[2].name }], defaults: { destination_id: 'destination-demo', driver_id: demoAccounts[1].id, receiver_id: demoAccounts[2].id } }
const demoTransferId = '33333333-3333-4333-8333-333333333333'
const demoTransfers = new Map([[demoTransferId, { id: demoTransferId, code: 'DEMO-ENTREGA-01', state: 'PENDIENTE_RECOGIDA', lock_version: 1, version_id: '44444444-4444-4444-8444-444444444444', units_presentation: 20, origin_name: 'Centro demo', destination_name: 'Punto de venta demo', driver_name: 'Cuenta demo transporte', receiver_name: 'Cuenta demo recepcion', correction_pending: false }]])
const demoCorrections = new Map<string, { id: string; transfer_id: string; original_quantity: number; proposed_quantity: number; reason: string; state: string; proposal_version_id: string; approver_transport: string; approver_reception: string; lock_version: number; decisions: { role: string; decision: string; user_id: string }[] }>()
demoTransfers.set('55555555-5555-4555-8555-555555555555', { id: '55555555-5555-4555-8555-555555555555', code: 'DEMO-EN-CAMINO', state: 'EN_CAMINO', lock_version: 2, version_id: '66666666-6666-4666-8666-666666666666', units_presentation: 15, origin_name: 'Centro demo', destination_name: 'Punto de venta demo', driver_name: 'Cuenta demo transporte', receiver_name: 'Cuenta demo recepcion', correction_pending: false })
const demoReceived = { id: '77777777-7777-4777-8777-777777777777', code: 'DEMO-RECIBIDA', state: 'RECIBIDO', lock_version: 4, version_id: '88888888-8888-4888-8888-888888888888', units_presentation: 18, original_quantity: 20, received_date: new Date().toISOString().slice(0, 10), origin_name: 'Centro demo', destination_name: 'Punto de venta demo', driver_name: 'Cuenta demo transporte', receiver_name: 'Cuenta demo recepcion', correction_pending: false }
const demoMilkings = new Map([['99999999-9999-4999-8999-999999999999', { id: '99999999-9999-4999-8999-999999999999', state: 'CONFIRMADA', center_id: 'center-demo', date: new Date().toISOString().slice(0, 10), shift_name: 'Diario demo', lock_version: 2, version_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', total_litres: '8.500', linked_litres: '0.000', details: [{ animal_id: 'demo-vaca-a', code: 'V-01 DEMO', litres: '0.000' }, { animal_id: 'demo-vaca-b', code: 'V-02 DEMO', litres: '8.500' }] }]])
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
  if (path === '/push/config' && method === 'GET') return json({ enabled: false, vapid_public_key: null })
  if (path === '/push/subscriptions' && method === 'GET') return json({ results: [] })
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
  if (path === '/lots' && method === 'GET') {
    if (!['PRODUCCION', 'ADMIN'].includes(session.assignments[0].role)) return error('PERMISSION_DENIED', 'Sin acceso a lotes.', 403)
    return json({ results: demoLots.filter(lot => session!.assignments[0].scope === 'GLOBAL' || lot.center_id === session!.assignments[0].location_id), next: null, count: 1 })
  }
  if (path === '/presentations' && method === 'GET') return json({ results: [demoPresentation], next: null, count: 1 })
  if (path === '/assignment-options' && method === 'GET') {
    if (!['PRODUCCION', 'ADMIN'].includes(session.assignments[0].role)) return error('PERMISSION_DENIED', 'Sin acceso a opciones.', 403)
    return json(demoOptions)
  }
  if (path.startsWith('/transfers/') && method === 'GET') {
    const record = demoTransfers.get(path.split('/')[2])
    if (!record) return error('VALIDATION_ERROR', 'Entrega no disponible en la demostración.', 404)
    if (!['PRODUCCION', 'ADMIN'].includes(session.assignments[0].role)) return error('PERMISSION_DENIED', 'No autorizado en esta demostración.', 403)
    return json(record)
  }
  if (path === '/transfers' && method === 'GET') {
    const role = session.assignments[0].role
    const params = new URL(input, 'http://localhost').searchParams
    const results = params.get('status') === 'RECIBIDO' ? [demoReceived].filter(item => item.received_date >= (params.get('from') ?? '') && item.received_date <= (params.get('to') ?? '9999-12-31')) : [...demoTransfers.values(), demoReceived]
    return json({ results: ['PRODUCCION', 'TRANSPORTE', 'RECEPCION', 'ADMIN'].includes(role) ? results : [], next: null, count: results.length })
  }
  if (path === '/metrics/transfers' && method === 'GET') {
    const params = new URL(input, 'http://localhost').searchParams
    const date = new Date().toISOString().slice(0, 10)
    const days = date >= (params.get('from') ?? '') && date <= (params.get('to') ?? '') ? [{ date, picked_litres: '15.000', received_litres: '0.000', transfers: [{ id: '55555555-5555-4555-8555-555555555555', code: 'DEMO-EN-CAMINO', picked_litres: '15.000', received_litres: '0.000', state: 'EN_CAMINO' }] }] : []
    return json({ days, cutoff_at: new Date().toISOString(), time_zone: 'America/Lima' })
  }
  if (path === '/metrics/milk' && method === 'GET') {
    if (!['PRODUCCION', 'ADMIN'].includes(session.assignments[0].role)) return error('PERMISSION_DENIED', 'Métricas no autorizadas.', 403)
    const date = new Date().toISOString().slice(0, 10)
    const params = new URL(input, 'http://localhost').searchParams
    const inside = date >= (params.get('from') ?? '') && date <= (params.get('to') ?? '')
    return json({ points: inside ? [{ date, animal_id: 'demo-vaca-a', code: 'V-01 DEMO', litres: '0.000' }, { date, animal_id: 'demo-vaca-b', code: 'V-02 DEMO', litres: '8.500' }] : [], days_registered: inside ? 1 : 0, expected_days: 30, total_litres: inside ? '8.500' : '0.000', average_per_registered_day: inside ? '8.500' : '0.000', cutoff_at: new Date().toISOString(), time_zone: 'America/Lima' })
  }
  if (path === '/milkings' && method === 'GET') {
    if (!['PRODUCCION', 'ADMIN'].includes(session.assignments[0].role)) return error('PERMISSION_DENIED', 'Sin acceso a producción.', 403)
    return json({ results: [...demoMilkings.values()], next: null, count: demoMilkings.size })
  }
  if (path.startsWith('/milkings/') && method === 'GET') {
    const found = demoMilkings.get(path.split('/')[2])
    if (!found || !['PRODUCCION', 'ADMIN'].includes(session.assignments[0].role)) return error('PERMISSION_DENIED', 'Producción no autorizada.', 403)
    return json(found)
  }
  if (path.startsWith('/milkings/') && method === 'POST' && (path.endsWith('/rectify') || path.endsWith('/void'))) {
    const found = demoMilkings.get(path.split('/')[2])
    if (!found || session.assignments[0].role !== 'PRODUCCION') return error('PERMISSION_DENIED', 'Solo producción puede corregir.', 403)
    if (found.lock_version !== data.expected_version) return error('VERSION_CONFLICT', 'La producción cambió; revisa versión actual.', 409)
    if (!data.payload?.reason?.trim()) return error('VALIDATION_ERROR', 'Motivo obligatorio.', 422)
    if (path.endsWith('/void')) {
      if (Number(found.linked_litres) > 0) return error('INVALID_STATE', 'Hay entregas publicadas vinculadas.', 409)
      found.state = 'ANULADA'
    } else {
      const details = data.payload?.details as typeof found.details
      if (!Array.isArray(details) || details.length !== found.details.length) return error('VALIDATION_ERROR', 'Detalle completo obligatorio.', 422)
      const total = details.reduce((sum, item) => sum + Number(item.litres), 0)
      if (total <= 0 || total < Number(found.linked_litres)) return error('ALLOCATION_EXCEEDED', 'El total debe cubrir entregas activas.', 409)
      found.details = details; found.total_litres = total.toFixed(3); found.version_id = data.payload.new_version_id
    }
    found.lock_version++
    return json({ event_id: data.event_id, entity_id: found.id, status: 'APLICADA', lock_version: found.lock_version, result: found, server_received_at: new Date().toISOString() })
  }
  if (path.startsWith('/transfers/') && method === 'POST' && (path.endsWith('/revise') || path.endsWith('/cancel'))) {
    const record = demoTransfers.get(path.split('/')[2])
    if (!record || session.assignments[0].role !== 'PRODUCCION') return error('PERMISSION_DENIED', 'Solo producción asignada puede revisar esta solicitud.', 403)
    if (record.state !== 'PENDIENTE_RECOGIDA') return error('INVALID_STATE', 'La entrega ya no espera recogida.', 409)
    if (record.lock_version !== data.expected_version || (path.endsWith('/revise') && data.payload?.version_id !== record.version_id)) return error('VERSION_CONFLICT', 'La solicitud cambió; revisa la cantidad actual.', 409)
    if (!data.payload?.reason) return error('VALIDATION_ERROR', 'Se necesita un motivo.', 422)
    if (path.endsWith('/revise')) { record.version_id = data.payload.new_version_id; record.units_presentation = data.payload.units_presentation }
    else record.state = 'CANCELADO'
    record.lock_version++
    return json({ event_id: data.event_id, status: 'APLICADA', entity_id: record.id, lock_version: record.lock_version, result: { ...record }, server_received_at: new Date().toISOString() })
  }
  if (path.startsWith('/transfers/') && path.endsWith('/corrections') && method === 'POST') {
    const record = demoTransfers.get(path.split('/')[2])
    if (!record || session.assignments[0].role !== 'PRODUCCION') return error('PERMISSION_DENIED', 'Solo producción de origen propone cambios.', 403)
    if (!['EN_CAMINO', 'RECIBIDO'].includes(record.state)) return error('INVALID_STATE', 'Solo después de recogida.', 409)
    if (record.lock_version !== data.expected_version) return error('VERSION_CONFLICT', 'La entrega cambió.', 409)
    if ([...demoCorrections.values()].some(item => item.transfer_id === record.id && item.state === 'PENDIENTE')) return error('CORRECTION_PENDING', 'Ya hay una corrección pendiente.', 409)
    if (!Number.isInteger(data.payload?.new_quantity) || data.payload.new_quantity <= 0 || !data.payload?.reason?.trim()) return error('VALIDATION_ERROR', 'Cantidad positiva y motivo son obligatorios.', 422)
    const correction = { id: data.payload.correction_id, transfer_id: record.id, original_quantity: record.units_presentation, proposed_quantity: data.payload.new_quantity, reason: data.payload.reason, state: 'PENDIENTE', proposal_version_id: data.payload.proposal_version_id, approver_transport: demoAccounts[1].id, approver_reception: demoAccounts[2].id, lock_version: 1, decisions: [] }
    demoCorrections.set(correction.id, correction)
    record.correction_pending = true
    record.lock_version++
    return json({ event_id: data.event_id, entity_id: record.id, status: 'APLICADA', lock_version: record.lock_version, result: correction, server_received_at: new Date().toISOString() })
  }
  if (path === '/corrections' && method === 'GET') return json({ results: [...demoCorrections.values()], next: null, count: demoCorrections.size })
  if (path.startsWith('/corrections/') && method === 'GET') {
    const found = [...demoCorrections.values()].find(item => item.id === path.split('/')[2])
    if (!found) return error('VALIDATION_ERROR', 'Corrección no encontrada.', 404)
    if (!['ADMIN', 'PRODUCCION'].includes(session.assignments[0].role) && ![found.approver_transport, found.approver_reception].includes(session.id)) return error('PERMISSION_DENIED', 'Sin acceso a la propuesta.', 403)
    return json(found)
  }
  if (path.startsWith('/corrections/') && path.endsWith('/withdraw') && method === 'POST') {
    const found = [...demoCorrections.values()].find(item => item.id === path.split('/')[2])
    if (!found || session.assignments[0].role !== 'PRODUCCION') return error('PERMISSION_DENIED', 'Solo solicitante puede retirar esta propuesta.', 403)
    if (found.state !== 'PENDIENTE' || data.expected_version !== found.lock_version) return error('VERSION_CONFLICT', 'La propuesta cambió de estado.', 409)
    if (!data.payload?.reason?.trim()) return error('VALIDATION_ERROR', 'Explica por qué retiras esta propuesta.', 422)
    found.state = 'RETIRADA'; found.lock_version++
    const transfer = demoTransfers.get(found.transfer_id)
    if (transfer) transfer.correction_pending = false
    return json({ event_id: data.event_id, entity_id: found.id, status: 'APLICADA', lock_version: found.lock_version, result: found, server_received_at: new Date().toISOString() })
  }
  if (path === '/devices' && method === 'POST') return json({ device_id: data.device_id, prepared_until: new Date(Date.now() + 7 * 86400000).toISOString() })
  if (path === '/sync/bootstrap') return json({ cursor: 'demo-1', prepared_until: new Date(Date.now() + 7 * 86400000).toISOString(), copies: [], tombstones: [] })
  if (path === '/sync/changes') return json({ cursor: 'demo-1', copies: [], tombstones: [] })
  return error('MOCK_NOT_IMPLEMENTED', 'Este punto del contrato aún no está implementado en la simulación.', 501)
}
