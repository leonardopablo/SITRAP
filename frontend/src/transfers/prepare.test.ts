import { defaults, validateBags } from './prepare'
import type { AssignmentOptions, Lot, Presentation } from './types'

const lot: Lot = { id: 'l', code: 'L', center_id: 'c', product_id: 'p', produced_litres: '23.500', unlinked_litres: '3.500', confirmed: true }
const presentation: Presentation = { id: 'b', product_id: 'p', name: 'Bolsa', content_base: '1.000', admits_fraction: false, active: true }
it('solo preselecciona opciones válidas y únicas', () => {
  const options: AssignmentOptions = { destinations: [{ id: 'd', name: 'Destino' }], drivers: [{ id: 't1', name: 'T1' }, { id: 't2', name: 'T2' }], receivers: [], defaults: { destination_id: 'obsoleto', driver_id: 't2' } }
  expect(defaults(options)).toEqual({ destination_id: 'd', driver_id: 't2', receiver_id: '' })
})
it('no permite fracciones de bolsa, sobreasignación ni producto distinto', () => {
  expect(validateBags('3', lot, presentation)).toBe(3)
  for (const amount of ['0', '-1', '1.5', '4', 'abc']) expect(() => validateBags(amount, lot, presentation)).toThrow()
  expect(() => validateBags('1', lot, { ...presentation, product_id: 'otro' })).toThrow()
})
