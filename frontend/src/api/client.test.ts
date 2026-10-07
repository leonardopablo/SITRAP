import { adaptResponse, createApiClient } from './client'
import { createCommand } from './commands'

it('normaliza HTML de error y fallo de red sin confundirlos con sesión', async () => {
  const transport = vi.fn().mockResolvedValueOnce(new Response('<html>Error</html>', { status: 503 })).mockRejectedValueOnce(new TypeError('fetch failed'))
  const client = createApiClient(transport)
  await expect(client.request('/animals')).rejects.toMatchObject({ status: 503, body: { code: 'HTTP_ERROR', retryable: true } })
  await expect(client.request('/animals')).rejects.toMatchObject({ status: 0, body: { code: 'NETWORK_ERROR', retryable: true } })
})

it('mantiene UUID y fotografía del payload en reintentos', async () => {
  const payload = { version_id: crypto.randomUUID() }
  const command = createCommand({ device_id: crypto.randomUUID(), entity_id: crypto.randomUUID(), type: 'TRANSFER_PICKUP', expected_version: 3, payload })
  const original = command.payload.version_id
  payload.version_id = crypto.randomUUID()
  const bodies: unknown[] = []
  const client = createApiClient(async (path, init) => {
    if (path.endsWith('/csrf')) return Response.json({ csrf_token: 'csrf' })
    bodies.push(JSON.parse(String(init?.body)))
    return Response.json({ event_id: command.event_id, status: 'APLICADA' })
  })
  await client.post('/transfers/test/pickup', command)
  await client.post('/transfers/test/pickup', command)
  expect(bodies[0]).toEqual(bodies[1])
  expect(command.payload.version_id).toBe(original)
  expect(command.event_id).toMatch(/^[0-9a-f-]{36}$/)
  expect(command.payload).not.toHaveProperty('actor')
})

it('sitúa cada etapa del viaje en su día físico de Lima', () => {
  const result = adaptResponse('/metrics/transfers', {
    days: [{ date: '2026-10-05', picked_up_liters: '3.000', received_liters: '0.000' }, { date: '2026-10-06', picked_up_liters: '0.000', received_liters: '3.000' }],
    records: [{ transfer_id: 'transfer', liters: '3.000', pickup_at: '2026-10-06T04:30:00Z', reception_at: '2026-10-06T16:00:00Z' }],
  }) as { days: { transfers: { picked_litres: string; received_litres: string }[] }[] }
  expect(result.days[0].transfers).toMatchObject([{ picked_litres: '3.000', received_litres: '0' }])
  expect(result.days[1].transfers).toMatchObject([{ picked_litres: '0', received_litres: '3.000' }])
})
