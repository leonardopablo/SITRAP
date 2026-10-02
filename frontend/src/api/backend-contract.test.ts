import { adaptResponse, backendPath } from './client'

it('adapta cuenta y documentos publicados del contrato Django, no un fixture con campos simulados', () => {
  const account = adaptResponse('/auth/me', { id: 'u', password_change_required: false, assignments: [{ id: 'a', role: 'TRANSPORTE', location_id: 'c' }], locations: [{ id: 'c', name: 'Kotosh' }] }) as any
  expect(account.change_password_required).toBe(false)
  expect(account.assignments[0].location_name).toBe('Kotosh')
  const transfer = adaptResponse('/transfers', { results: [{ id: 't', state: 'PENDIENTE_RECOGIDA', lock_version: 2, version_id: 'v', pending_correction_id: null, current_version: { origin_id: 'c', destination_id: 'p', driver_id: 'u', receiver_id: 'r', lines: [{ units: '20.000', quantity: '20.000' }] } }] }) as any
  expect(transfer.results[0]).toMatchObject({ units_presentation: 20, correction_pending: false, version_id: 'v' })
  expect(backendPath('/metrics/transfers?from=2026-10-01&to=2026-10-02')).toBe('/metrics/transfers?date_from=2026-10-01&date_to=2026-10-02')
})
