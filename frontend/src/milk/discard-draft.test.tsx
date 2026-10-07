import { act, cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, vi } from 'vitest'
import { api } from '../api/client'
import { createCommand } from '../api/commands'
import { db, readCopy, saveCopy } from '../offline/db'
import { ProductionHistory } from './ProductionHistory'
import { ProductionRevision } from './ProductionRevision'

vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ account: { id: 'discard-test' } }) }))
vi.mock('../auth/workspace', () => ({ useWorkspace: () => ({ assignment: { role: 'PRODUCCION', location_id: 'center' } }) }))

const id = '99999999-9999-4999-8999-999999999998'
const draft = { id, center_id: 'center', date: '2026-10-08', shift_name: 'Mañana', state: 'BORRADOR', lock_version: 1,
  version_id: 'version', total_litres: '82.000', linked_litres: null, details: [{ animal_id: 'cow', code: 'V1', litres: null }] }

function show(path = `/producciones/${id}`) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/historial" element={<ProductionHistory />} />
    <Route path="/producciones/:id" element={<ProductionRevision />} />
  </Routes></MemoryRouter></QueryClientProvider>)
}

afterEach(async () => {
  cleanup()
  vi.restoreAllMocks()
  await db.copies.delete(JSON.stringify(['discard-test', 'milking-draft', 'center']))
  await db.events.where('account_id').equals('discard-test').delete()
  await db.devices.delete('discard-test')
})

it('ofrece descartar el borrador en historial y conserva los confirmados', async () => {
  vi.spyOn(api, 'request').mockResolvedValue({ results: [draft, { ...draft, id: crypto.randomUUID(), state: 'CONFIRMADA' }], next: null, count: 2 })
  show('/historial')
  expect(await screen.findByRole('link', { name: 'Descartar borrador' })).toHaveAttribute('href', `/producciones/${id}`)
  expect(screen.getAllByRole('link', { name: 'Descartar borrador' })).toHaveLength(1)
})

it('anula un borrador incompleto y limpia solo su puntero local tras el acuse', async () => {
  vi.spyOn(api, 'request').mockResolvedValue(draft)
  const post = vi.spyOn(api, 'post').mockResolvedValue({ status: 'APLICADA' })
  await db.devices.put({ account_id: 'discard-test', device_id: 'device', registered: true, prepared_until: null })
  await saveCopy('discard-test', 'milking-draft', 'center', { id, date: draft.date })
  show()
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'Descartar borrador' }))
  await user.type(screen.getByLabelText('Motivo'), 'Fecha incorrecta')
  await act(async () => { await user.click(screen.getByRole('button', { name: 'Confirmar descarte' })) })
  expect(await screen.findByText('Cambio simulado en memoria, NO aplicado en SITRAP.')).toBeVisible()
  expect(post).toHaveBeenCalledWith(`/milkings/${id}/void`, expect.objectContaining({ type: 'MILKING_VOID', entity_id: id, payload: { reason: 'Fecha incorrecta' } }))
  expect(await readCopy('discard-test', 'milking-draft', 'center')).toBeUndefined()
})

it('no descarta mientras haya operaciones locales de ese ordeño pendientes', async () => {
  vi.spyOn(api, 'request').mockResolvedValue(draft)
  const post = vi.spyOn(api, 'post')
  await db.devices.put({ account_id: 'discard-test', device_id: 'device', registered: true, prepared_until: null })
  const command = createCommand({ type: 'MILKING_CONFIRM', entity_id: id, device_id: 'device', expected_version: 1, payload: { version_id: 'version', lot_id: 'lot' } })
  await db.events.put({ event_id: command.event_id, account_id: 'discard-test', device_id: 'device', command, status: 'PENDIENTE', created_at: new Date().toISOString(), updated_at: new Date().toISOString() })
  show()
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'Descartar borrador' }))
  await user.type(screen.getByLabelText('Motivo'), 'No corresponde')
  await user.click(screen.getByRole('button', { name: 'Confirmar descarte' }))
  expect(await screen.findByText(/Hay operaciones de este borrador pendientes/)).toBeVisible()
  expect(post).not.toHaveBeenCalled()
})
