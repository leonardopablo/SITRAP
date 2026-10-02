import { accountCreationBlocker } from './accountValidation'

it('explica por qué aún no se puede crear una cuenta real', () => {
  expect(accountCreationBlocker(false, 'vilma', 'Vilma', 'TemporalSegura123!', 'http')).toMatch(/Sin conexión/)
  expect(accountCreationBlocker(true, '', 'Vilma', 'TemporalSegura123!', 'http')).toMatch(/usuario/)
  expect(accountCreationBlocker(true, 'vilma', ' ', 'TemporalSegura123!', 'http')).toMatch(/nombre/)
  expect(accountCreationBlocker(true, 'vilma', 'Vilma', 'abc', 'http')).toContain('faltan 9')
  expect(accountCreationBlocker(true, 'vilma', 'Vilma', 'TemporalSegura123!', 'http')).toBe('')
})
