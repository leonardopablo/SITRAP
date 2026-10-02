import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { api } from '../api/client'
import { demoAccounts, seedDemoNotifications } from '../api/mock'
import { AuthProvider } from '../auth/AuthProvider'
import { InboxBell, InboxPage } from './Inbox'

it('marcar leído reduce contador sin afirmar que una entrega fue confirmada', async () => {
  const account = demoAccounts[1]
  seedDemoNotifications(account.id, [{ id: crypto.randomUUID(), type: 'PICKUP_REQUESTED', title: 'Solicitud pendiente', text: 'Tienes una entrega', created_at: new Date().toISOString(), read_at: null, entity_type: 'transfer', entity_id: crypto.randomUUID(), version_id: null }])
  await api.post('/auth/login', { username: 'transporte', password: 'Demostracion123!' })
  await act(async () => { render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AuthProvider><InboxBell /><InboxPage /></AuthProvider></MemoryRouter></QueryClientProvider>) })
  expect(await screen.findByRole('link', { name: 'Avisos, 1 no leídos' })).toBeVisible()
  expect(screen.getByText('Leer un aviso no confirma una recogida, recepción ni corrección.')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: 'Marcar leído' }))
  expect(await screen.findByRole('link', { name: 'Avisos, 0 no leídos' })).toBeVisible()
  expect(screen.getByText('Leído')).toBeVisible()
  await api.post('/auth/logout')
})
