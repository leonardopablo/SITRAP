import { monthRange, sumMetric } from './calendar'

it('rango mensual usa días UTC sin saltos de horario y separa medidas', () => {
  expect(monthRange(2024, 1)).toMatchObject({ from: '2024-02-01', to: '2024-02-29', days: 29 })
  expect(monthRange(2026, 0)).toMatchObject({ from: '2026-01-01', to: '2026-01-31', days: 31 })
  const day = [{ date: '2026-01-01', picked_litres: '2.500', received_litres: '1.000', transfers: [] }]
  expect(sumMetric(day, 'picked_litres')).not.toBe(sumMetric(day, 'received_litres'))
})
