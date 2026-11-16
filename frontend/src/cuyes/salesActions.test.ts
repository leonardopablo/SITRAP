import { describe, expect, it } from 'vitest'
import { enqueue, getDevice, SitrapDB } from '../offline/db'
import { createCommand } from '../api/commands'
import { createApiClient } from '../api/client'
import { suggestFifo } from './salesActions'
import type { Candidate, Sale } from './salesTypes'

describe('Ventas de cuyes', () => {
  it('sugiere FIFO estable repartido sin usar dos veces un mismo saldo para ítems competidores', () => {
    const order = { lines: [
      { id: 'kit', units: 2, recipe: [{ category: 'MACHO', quality: 'A', quantity: 1 }, { category: 'HEMBRA', quality: 'A', quantity: 3 }] },
      { id: 'unit', units: 1, recipe: [{ category: 'MACHO', quality: 'A', quantity: 1 }] },
    ], preparation: null } as unknown as Sale
    const candidates = [
      { occupation_id: 'old', category: 'MACHO', quality: 'A', available: 2, opened_on: '2026-01-01' },
      { occupation_id: 'new', category: 'MACHO', quality: 'A', available: 2, opened_on: '2026-02-01' },
      { occupation_id: 'females', category: 'HEMBRA', quality: 'A', available: 6, opened_on: '2026-01-01' },
    ] as Candidate[]
    const suggestion = suggestFifo(order, candidates)
    expect(suggestion.find(i => i.line_id === 'kit' && i.category === 'MACHO')?.occupation_id).toBe('old')
    expect(suggestion.find(i => i.line_id === 'unit')?.occupation_id).toBe('new')
    expect(suggestion.reduce((sum, i) => sum + i.quantity, 0)).toBe(9)
    expect(() => suggestFifo(order, candidates.filter(c => c.occupation_id !== 'new'))).toThrow('No alcanza')
  })
  it('no vuelve a asignar lo ya seleccionado por otros galpones', () => {
    const order = { lines: [{ id: 'line', units: 5, recipe: [{ category: 'MACHO', quality: 'B', quantity: 1 }] }], preparation: { other_allocations: [{ line_id: 'line', category: 'MACHO', quality: 'B', quantity: 3 }] } } as unknown as Sale
    expect(suggestFifo(order, [{ occupation_id: 'own', category: 'MACHO', quality: 'B', available: 2 }] as Candidate[])[0].quantity).toBe(2)
  })
  it('rechaza la captura comercial en IndexedDB aunque el dispositivo esté preparado', async () => {
    const store = new SitrapDB(`sale-test-${crypto.randomUUID()}`)
    try {
      const d = await getDevice('account', store)
      await store.devices.update('account', { registered: true, prepared_until: new Date(Date.now() + 86400000).toISOString() })
      const c = createCommand({ type: 'SALE_PAY', entity_id: crypto.randomUUID(), device_id: d.device_id, payload: {} })
      await expect(enqueue('account', c, store)).rejects.toThrow('requieren conexión')
      expect(await store.events.count()).toBe(0)
    } finally { await store.delete() }
  })
  it('envía comprobantes como multipart sin fijar Content-Type JSON y conserva CSRF', async () => {
    const requests: RequestInit[] = []
    const client = createApiClient(async (path, init) => {
      if (path.endsWith('/auth/csrf')) return Response.json({ csrf_token: 'test-token' })
      requests.push(init ?? {})
      return Response.json({ id: 'voucher' })
    })
    const data = new FormData()
    data.set('file', new File(['%PDF-1.4'], 'voucher.pdf'))
    await client.request('/cuyes/sales/vouchers', { method: 'POST', body: data })
    const headers = requests[0].headers as Record<string, string>
    expect(headers['Content-Type']).toBeUndefined()
    expect(headers['X-CSRFToken']).toBe('test-token')
    expect(requests[0].body).toBe(data)
  })
})
