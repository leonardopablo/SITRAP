import { render, screen } from '@testing-library/react'
import { Logo } from './Logo'

it('usa el logo completo en cabecera y el símbolo compacto con nombre accesible', () => {
  const { rerender } = render(<Logo />)
  expect(screen.getByRole('img', { name: 'SITRAP' })).toHaveAttribute('src', '/brand/sitrap-logo.svg')
  rerender(<Logo compact />)
  expect(screen.getByRole('img', { name: 'SITRAP' })).toHaveAttribute('src', '/brand/sitrap-icon.svg')
})
