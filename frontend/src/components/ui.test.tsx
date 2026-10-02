import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button, Field } from './ui'

it('asocia etiqueta y error al campo y permite foco por teclado', async () => {
  render(<Field label="Litros" error="Revisa la cantidad" />)
  await userEvent.tab()
  expect(screen.getByLabelText('Litros')).toHaveFocus()
  expect(screen.getByLabelText('Litros')).toHaveAccessibleDescription('Revisa la cantidad')
})

it('bloquea nuevos clics durante el envío', async () => {
  const send = vi.fn()
  render(<Button busy onClick={send}>Confirmando…</Button>)
  await userEvent.click(screen.getByRole('button'))
  expect(send).not.toHaveBeenCalled()
})
