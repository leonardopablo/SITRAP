import { cowTotals } from './milk'

it('mantiene cero explícito, ausente y versiones vigentes sin sumar puntos nulos', () => {
  const result = cowTotals([{ animal_id: 'a', code: 'A', date: '2026-10-01', litres: null }, { animal_id: 'a', code: 'A', date: '2026-10-02', litres: '0.000' }, { animal_id: 'b', code: 'B', date: '2026-10-02', litres: '2.125' }])
  expect(result).toEqual([{ code: 'A', litres: 0, registered: 1 }, { code: 'B', litres: 2.125, registered: 1 }])
})
