import { pushSupported, vapidBytes } from './subscription'

it('decodifica clave pública URL-safe sin solicitar permiso', () => {
  expect(Array.from(vapidBytes('AQIDBA'))).toEqual([1, 2, 3, 4])
  expect(pushSupported()).toBe(false)
})
