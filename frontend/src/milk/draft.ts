import type { Animal } from '../animals/types'

/** Integer millilitres, no floating-point rounding and blank != zero. */
export function parseLitres(value: string): number | null {
  if (value === '') return null
  if (!/^(0|[1-9]\d*)(?:[.,]\d{1,3})?$/.test(value)) throw new Error('Usa litros no negativos, con hasta tres decimales.')
  const [whole, fraction = ''] = value.replace(',', '.').split('.')
  const ml = Number(whole) * 1000 + Number(fraction.padEnd(3, '0'))
  if (!Number.isSafeInteger(ml) || ml > 99999999999999) throw new Error('Cantidad fuera del rango permitido.')
  return ml
}
export function formatLitres(ml: number) { return `${(ml / 1000).toLocaleString('es-PE', { minimumFractionDigits: 0, maximumFractionDigits: 3 })} L` }
export function draftDetails(animals: Animal[], values: Record<string, string>) {
  return animals.map(animal => ({ animal_id: animal.id, litros: values[animal.id] === '' ? null : ((parseLitres(values[animal.id] ?? '') ?? 0) / 1000).toFixed(3) }))
}
export function confirmable(animals: Animal[], values: Record<string, string>) {
  if (!animals.length) return false
  let total = 0
  for (const animal of animals) {
    const litres = parseLitres(values[animal.id] ?? '')
    if (litres === null) return false
    total += litres
  }
  return total > 0
}
