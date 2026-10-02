export interface MilkPoint { date: string; animal_id: string; code: string; litres: string | null }
export interface MilkMetrics { points: MilkPoint[]; days_registered: number; expected_days: number; total_litres: string; average_per_registered_day: string; cutoff_at: string; time_zone: string }
export function cowTotals(points: MilkPoint[]) {
  const result = new Map<string, { code: string; ml: number; registered: number }>()
  for (const point of points) {
    const item = result.get(point.animal_id) ?? { code: point.code, ml: 0, registered: 0 }
    if (point.litres !== null) { item.ml += Math.round(Number(point.litres) * 1000); item.registered++ }
    result.set(point.animal_id, item)
  }
  return [...result.values()].map(item => ({ code: item.code, litres: item.ml / 1000, registered: item.registered }))
}
