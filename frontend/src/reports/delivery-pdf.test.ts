import { createApiClient } from '../api/client'

it('PDF de transporte y recepción requieren contenido PDF y rutas protegidas', async () => {
  const transport = vi.fn(async (_url: string) => new Response('%PDF-1.7', { headers: { 'Content-Type': 'application/pdf' } }))
  const client = createApiClient(transport)
  await client.pdf('/reports/transfers.pdf?from=2026-10-01&to=2026-10-31')
  await client.pdf('/reports/receptions.pdf?from=2026-10-01&to=2026-10-31')
  expect(transport.mock.calls.map(call => call[0])).toEqual(['/api/v1/reports/transfers.pdf?from=2026-10-01&to=2026-10-31', '/api/v1/reports/receptions.pdf?from=2026-10-01&to=2026-10-31'])
})
