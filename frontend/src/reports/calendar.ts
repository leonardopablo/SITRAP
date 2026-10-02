export interface DayMetric { date: string; picked_litres: string; received_litres: string; transfers: { id: string; code: string; picked_litres: string; received_litres: string; state: string }[] }
export interface TransferMetrics { days: DayMetric[]; cutoff_at: string; time_zone: string }
export function monthRange(year: number, month: number) {
  const first = new Date(Date.UTC(year, month, 1))
  const next = new Date(Date.UTC(year, month + 1, 1))
  return { from: first.toISOString().slice(0, 10), to: new Date(next.getTime() - 86400000).toISOString().slice(0, 10), days: Math.round((next.getTime() - first.getTime()) / 86400000) }
}
export function monthLabel(year: number, month: number) { return new Intl.DateTimeFormat('es-PE', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(year, month, 1))) }
export function sumMetric(days: DayMetric[], key: 'picked_litres' | 'received_litres') { return (days.reduce((sum, day) => sum + Math.round(Number(day[key]) * 1000), 0) / 1000).toLocaleString('es-PE', { maximumFractionDigits: 3 }) }
