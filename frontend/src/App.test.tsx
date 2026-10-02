import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { App } from './App'

it('navega al acceso sin recargar la aplicación', async () => {
  render(<MemoryRouter><App /></MemoryRouter>)
  await userEvent.click(screen.getByRole('link', { name: 'Ingresar' }))
  expect(screen.getByRole('heading', { name: 'Acceso a SITRAP' })).toBeVisible()
})

it('ofrece recuperación para una ruta desconocida', () => {
  render(<MemoryRouter initialEntries={['/desconocida']}><App /></MemoryRouter>)
  expect(screen.getByRole('heading', { name: 'Página no encontrada' })).toBeVisible()
})
