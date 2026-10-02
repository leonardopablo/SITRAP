import type { AssignmentOptions, Lot, Presentation } from './types'

export function defaults(options: AssignmentOptions) {
  const valid = (values: { id: string }[], selected?: string) => values.find(item => item.id === selected)?.id ?? (values.length === 1 ? values[0].id : '')
  return { destination_id: valid(options.destinations, options.defaults?.destination_id), driver_id: valid(options.drivers, options.defaults?.driver_id), receiver_id: valid(options.receivers, options.defaults?.receiver_id) }
}
export function validateBags(bags: string, lot: Lot, presentation: Presentation) {
  if (!/^\d+$/.test(bags) || Number(bags) <= 0 || !Number.isSafeInteger(Number(bags))) throw new Error('Escribe un número entero de bolsas mayor que cero.')
  if (presentation.admits_fraction || presentation.content_base !== '1.000' || presentation.product_id !== lot.product_id) throw new Error('El piloto solo permite bolsas indivisibles de 1 L del mismo producto.')
  const availableMl = Math.round(Number(lot.unlinked_litres) * 1000)
  if (Number(bags) * 1000 > availableMl) throw new Error('La cantidad supera los litros no vinculados del lote. Revisa el dato actual.')
  return Number(bags)
}
