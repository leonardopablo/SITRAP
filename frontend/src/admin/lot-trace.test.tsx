import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, vi } from 'vitest'
import { api } from '../api/client'
import { LotTracePage } from './LotTracePage'

vi.mock('../api/client', async importOriginal => ({ ...await importOriginal<typeof import('../api/client')>(), apiMode: 'http' }))
vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ account: { id: 'admin-1' } }) }))
vi.mock('../offline/SyncPanel', () => ({ useConnection: () => true }))

const lotId = '593de4d2-d933-4f2a-a793-0b21d2896d78'
const trace = {
  lot: { id: lotId, code: 'L-20261009-ABC', production_id: 'production-1', state: 'CONFIRMADA', date: '2026-10-09', confirmed_at: '2026-10-09T14:00:00Z', center_name: 'Kotosh', turn_name: 'Mañana', responsible_name: 'Vilma', quantity: '88.000' },
  count: 2, draft_count: 4, next_offset: null, transfers: [
    { id: 'transfer-1', code: 'T-01', state: 'RECIBIDO', quantity: '50.000', origin_name: 'Kotosh', destination_name: 'Punto de venta', driver_name: 'Lolo', receiver_name: 'María', request_at: '2026-10-09T14:10:00Z', pickup: { at: '2026-10-09T15:00:00Z', registered_at: '2026-10-09T16:00:00Z', actor_name: 'Lolo' }, reception: { at: '2026-10-09T16:45:00Z', registered_at: '2026-10-09T18:00:00Z', actor_name: 'María' }, travel_minutes: 105, inconsistent_time: false, has_history: true },
    { id: 'transfer-2', code: 'T-02', state: 'PENDIENTE_RECOGIDA', quantity: '20.000', origin_name: 'Kotosh', destination_name: 'Otro punto', driver_name: 'Lolo', receiver_name: 'María', request_at: '2026-10-09T17:00:00Z', pickup: null, reception: null, travel_minutes: null, inconsistent_time: false, has_history: false },
  ],
}

function show(path: string) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/administracion/lotes" element={<LotTracePage />} />
    <Route path="/administracion/lotes/:id" element={<LotTracePage />} />
  </Routes></MemoryRouter></QueryClientProvider>)
}

afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('permite buscar un lote y abrir su recorrido desde administración', async () => {
  const request = vi.spyOn(api, 'request').mockImplementation(async (path: string) => path.startsWith('/lots?') ? { results: [{ id: lotId, code: trace.lot.code, date: trace.lot.date, quantity: trace.lot.quantity, production_state: 'CONFIRMADA' }], count: 1, next: null } as never : trace as never)
  show('/administracion/lotes')
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Buscar por código de lote'), '20261009')
  await user.click(screen.getByRole('button', { name: 'Buscar lote' }))
  expect(await screen.findByRole('link', { name: /L-20261009-ABC/ })).toBeVisible()
  expect(request).toHaveBeenCalledWith(expect.stringContaining('code=20261009'))
  await user.click(screen.getByRole('link', { name: /L-20261009-ABC/ }))
  expect(await screen.findByRole('heading', { name: 'Lote L-20261009-ABC' })).toBeVisible()
  expect(screen.getByText(/Responsable:/)).toHaveTextContent('Vilma')
})

it('muestra ramas separadas, duración y estado pendiente sin inventar una hora', async () => {
  vi.spyOn(api, 'request').mockResolvedValue(trace)
  show(`/administracion/lotes/${lotId}`)
  const received = await screen.findByRole('article', { name: /Kotosh.*Punto de venta/ })
  expect(within(received).getByText(/1 h 45 min/)).toBeVisible()
  expect(within(received).getByText(/tuvo revisiones o correcciones/)).toBeVisible()
  const pending = screen.getByRole('article', { name: /Kotosh.*Otro punto/ })
  expect(within(pending).getByText(/Pendiente de ambas confirmaciones/)).toBeVisible()
  expect(screen.getByText('2 entregas')).toBeVisible()
  expect(screen.getByText(/4 borradores de entrega no enviados/)).toBeVisible()
})
