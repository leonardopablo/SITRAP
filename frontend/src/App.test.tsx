import { act, render, screen, within } from '@testing-library/react'
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
  const username = screen.getByLabelText('Usuario')
  const password = screen.getByLabelText('Contraseña')
  expect(username).not.toHaveAttribute('readonly')
  await userEvent.type(username, 'admin')
  await userEvent.type(password, 'una-clave')
  expect(username).toHaveValue('admin')
  expect(password).toHaveValue('una-clave')
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

it('permite al administrador encontrar y abrir la creación de cuentas desde su resumen', async () => {
  await api.post('/auth/login', { username: 'admin', password: 'Demostracion123!' })
  await act(async () => { renderApp('/administracion') })
  expect(await screen.findByRole('link', { name: 'Crear cuentas y asignar funciones' })).toBeVisible()
  await userEvent.click(screen.getByRole('link', { name: 'Crear cuentas y asignar funciones' }))
  expect(await screen.findByRole('heading', { name: 'Crear cuenta' })).toBeVisible()
  expect(screen.getByRole('link', { name: 'Cuentas' })).toBeVisible()
  const nav = screen.getByRole('navigation', { name: 'Navegación principal' })
  expect(within(nav).getAllByRole('link')).toHaveLength(8)
  expect(within(nav).getByRole('link', { name: 'Cuyes' })).toHaveAttribute('href', '/cuyes')
  expect(within(nav).getByRole('link', { name: 'Cuentas' })).toHaveAttribute('aria-current', 'page')
  expect(within(nav).getAllByRole('link').every(link => link.querySelector('svg[aria-hidden="true"]'))).toBe(true)
  await userEvent.click(within(nav).getByRole('link', { name: 'Ayuda' }))
  expect(await screen.findByRole('heading', { name: 'Cómo usar SITRAP' })).toBeVisible()
  expect(screen.getByRole('heading', { name: 'Trazabilidad' })).toBeVisible()
  await api.post('/auth/logout')
})

it('permite a producción recuperar un borrador de entrega desde Hoy', async () => {
  await api.post('/auth/login', { username: 'produccion', password: 'Demostracion123!' })
  await act(async () => { renderApp('/hoy') })
  expect(await screen.findByRole('heading', { name: 'Entregas pendientes de enviar' })).toBeVisible()
  expect(await screen.findByText(/todavía no se notificó al conductor/)).toBeVisible()
  const review = screen.getByRole('link', { name: 'Revisar y enviar' })
  expect(review).toHaveAttribute('href', '/entregas/77777777-7777-4777-8777-777777777777')
  await userEvent.click(review)
  expect(await screen.findByRole('heading', { name: 'DEMO-BORRADOR-01' })).toBeVisible()
  expect(screen.getByRole('button', { name: 'Enviar solicitud a transporte' })).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: 'Descartar borrador' }))
  await userEvent.type(screen.getByLabelText('Motivo obligatorio'), 'Borrador de demostración antiguo')
  await userEvent.click(screen.getByRole('button', { name: 'Confirmar descarte' }))
  expect(await screen.findByText(/Borrador descartado/)).toBeVisible()
  await api.post('/auth/logout')
})
