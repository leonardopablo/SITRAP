import { createApiClient } from '../api/client'

it('descarga solo MIME PDF y envía cookies al mismo origen', async () => {
  const transport = vi.fn(async (_input: string, _init?: RequestInit) => new Response(new Blob(['%PDF-1.7'], { type: 'application/pdf' }), { headers: { 'Content-Type': 'application/pdf' } }))
  const client = createApiClient(transport)
  expect((await client.pdf('/reports/production.pdf?from=2026-10-01')).type).toBe('application/pdf')
  expect(transport.mock.calls[0][1]).toMatchObject({ credentials: 'same-origin' })
  await expect(client.pdf('/users/secret.pdf')).rejects.toThrow('no autorizado')
})

it('no presenta JSON o HTML de error como documento', async () => {
  const client = createApiClient(async () => new Response('error', { headers: { 'Content-Type': 'text/html' } }))
  await expect(client.pdf('/reports/production.pdf')).rejects.toThrow('no devolvió un PDF')
})
