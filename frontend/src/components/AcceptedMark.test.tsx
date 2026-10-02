import { render, screen } from '@testing-library/react'
import { AcceptedMark } from './AcceptedMark'

it('ofrece texto de aceptación; la marca animada es decorativa', () => {
  render(<AcceptedMark label="Recogida aceptada por el servidor" />)
  expect(screen.getByRole('status')).toHaveTextContent('Recogida aceptada por el servidor')
  expect(screen.getByText('✓')).toHaveAttribute('aria-hidden', 'true')
})
