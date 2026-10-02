import { confirmable, draftDetails, formatLitres, parseLitres } from './draft'

it('mantiene vacío distinto de cero y suma mililitros sin redondear flotantes', () => {
  expect(parseLitres('')).toBeNull()
  expect(parseLitres('0')).toBe(0)
  expect(parseLitres('0,125')).toBe(125)
  expect(parseLitres('23.500')).toBe(23500)
  expect(formatLitres(23625)).toContain('23')
  expect(draftDetails([{ id: 'a', code: 'A', name: null, center_id: 'x', center_name: 'X', species_id: 'cow', sex: 'HEMBRA', status: 'ACTIVO' }], { a: '' })).toEqual([{ animal_id: 'a', litros: null }])
  expect(draftDetails([{ id: 'a', code: 'A', name: null, center_id: 'x', center_name: 'X', species_id: 'cow', sex: 'HEMBRA', status: 'ACTIVO' }], { a: '0' })).toEqual([{ animal_id: 'a', litros: '0.000' }])
})
it('rechaza más de tres decimales, negativos y datos inválidos', () => {
  for (const value of ['-1', '1.2345', 'abc', '1e4']) expect(() => parseLitres(value)).toThrow()
})
it('confirma solo detalles completos y total positivo; cero explícito no es ausencia', () => {
  const animals = [{ id: 'a' }, { id: 'b' }] as Parameters<typeof confirmable>[0]
  expect(confirmable(animals, { a: '0', b: '' })).toBe(false)
  expect(confirmable(animals, { a: '0', b: '0' })).toBe(false)
  expect(confirmable(animals, { a: '0', b: '2,125' })).toBe(true)
})
