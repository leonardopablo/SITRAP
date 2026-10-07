import { act, cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { MilkingDraftPage } from './MilkingDraftPage'
import { db, readCopy, saveCopy } from '../offline/db'

vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ account: { id: 'account' } }) }))
vi.mock('../auth/workspace', () => ({ useWorkspace: () => ({ assignment: { id: 'role', location_id: 'center', location_name: 'Canchán' } }) }))
vi.mock('../offline/SyncPanel', () => ({ useConnection: () => false }))
vi.mock('dexie-react-hooks', () => ({ useLiveQuery: () => ({ status: 'APLICADA' }) }))

it('inicia otro ordeño sin reutilizar el confirmado ni borrar su operación', async () => {
  const eventId = crypto.randomUUID()
  await saveCopy('account', 'milking-draft', 'center', {
    id: 'old-milking', production_id: 'old-production', product_id: 'milk', version_id: 'old-version', center_id: 'center',
    date: '2026-10-03', shift_id: 'morning', values: { cow: '15' }, last_event_id: 'old-event', next_version: 2,
    confirm_event_id: eventId, lot_id: 'old-lot',
  })
  await db.events.put({ event_id: eventId, account_id: 'account', device_id: 'device', status: 'APLICADA',
    command: { event_id: eventId, device_id: 'device', type: 'MILKING_CONFIRM', entity_id: 'old-milking', occurred_at: new Date().toISOString(), depends_on: [], payload: { version_id: 'old-version', lot_id: 'old-lot' }, expected_version: 2 },
    created_at: new Date().toISOString(), updated_at: new Date().toISOString() })
  try {
    await act(async () => { render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><MilkingDraftPage /></MemoryRouter></QueryClientProvider>) })
    const button = await screen.findByRole('button', { name: 'Iniciar otro ordeño' })
    await userEvent.click(button)
    expect(await screen.findByLabelText('Fecha de ordeño')).toBeVisible()
    expect(await readCopy('account', 'milking-draft', 'center')).toBeUndefined()
    expect(await db.events.get(eventId)).toMatchObject({ status: 'APLICADA', command: { entity_id: 'old-milking' } })
  } finally {
    cleanup()
    await db.copies.delete(JSON.stringify(['account', 'milking-draft', 'center']))
    await db.events.delete(eventId)
  }
})
