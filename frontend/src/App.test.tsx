import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { App } from './App'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './auth/AuthProvider'
import { WorkspaceProvider } from './auth/workspace'
import { api } from './api/client'

function renderApp(path = '/') {
  return render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={[path]}><AuthProvider><WorkspaceProvider><App /></WorkspaceProvider></AuthProvider></MemoryRouter></QueryClientProvider>)
}

it('navega al acceso sin recargar la aplicación', async () => {
  renderApp()
  await userEvent.click(screen.getByRole('link', { name: 'Ingresar' }))
  expect(screen.getByRole('heading', { name: 'Acceso a SITRAP' })).toBeVisible()
})

it('bloquea rutas de otro rol y limpia cuenta y ámbito al salir', async () => {
  await api.post('/auth/login', { username: 'transporte', password: 'Demostracion123!' })
  await act(async () => { renderApp('/administracion') })
  expect(await screen.findByRole('heading', { name: 'Hoy' })).toBeVisible()
  expect(screen.queryByRole('link', { name: 'Administrar' })).not.toBeInTheDocument()
  expect(screen.getByText('@transporte')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
  expect(await screen.findByRole('heading', { name: 'Acceso a SITRAP' })).toBeVisible()
  expect(screen.queryByText('@transporte')).not.toBeInTheDocument()
})

it('ofrece recuperación para una ruta desconocida', async () => {
  await act(async () => { renderApp('/desconocida') })
  expect(screen.getByRole('heading', { name: 'Página no encontrada' })).toBeVisible()
})

it('muestra errores de login y obliga a cambiar la contraseña temporal', async () => {
  await act(async () => { renderApp('/acceso') })
  await userEvent.type(screen.getByLabelText('Usuario'), 'produccion')
  await userEvent.type(screen.getByLabelText('Contraseña'), 'incorrecta')
  await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Usuario o contraseña incorrectos')
  await userEvent.type(screen.getByLabelText('Contraseña'), 'Temporal123!')
  await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))
  expect(await screen.findByRole('heading', { name: 'Cambiar contraseña' })).toBeVisible()
})
