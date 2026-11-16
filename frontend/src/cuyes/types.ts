import type { components as Backend } from '../api/backend.generated'
export type CuyType = Backend['schemas']['CuyCommandRequest']['type']
export const cuyTypes = ['CUY_OPEN', 'CUY_BIRTH', 'CUY_DEATH', 'CUY_WEAN', 'CUY_MOVE', 'CUY_DISPATCH', 'CUY_RECEIVE', 'CUY_REDIRECT', 'CUY_RECLASS', 'CUY_COUNT', 'CUY_REVIEW', 'CUY_CLOSE', 'CUY_REOPEN', 'CUY_RESOLVE', 'CUY_ALERTS', 'CUY_COMPENSATE'] as const satisfies readonly CuyType[]
export type Category = 'MACHO' | 'HEMBRA' | 'LACTANTE'
export type Quality = 'A' | 'B' | 'C' | 'SIN_CLASIFICAR'
export interface Bucket { occupation_id?: string; pen_id?: string; category: Category; quality: Quality; quantity: number }
export interface Lot { id: string; provenance: string; opened_on: string; born_from: string | null; born_until: string | null; installed_on: string | null; age_days_min: number | null; age_days_max: number | null; rearing_days: number; reproductive_days: number | null; parent_id: string | null; source_occupation_id: string | null }
export interface Occupation { id: string; lot: Lot; started_on: string; closed_on: string | null; balances: { category: Category; quality: Quality; quantity: number }[] }
export type Pen = Backend['schemas']['PenOutput']
export interface Shed { id: string; center_id: string; code: string; name: string; active: boolean }
export interface Destination { id: string; code: string; shed_id: string; center_id: string; purpose: string; capacity: number }
export interface Transfer { id: string; source_id: string; source: string; destination_id: string; destination: string; state: string; items: Bucket[] }
export interface Count { id: string; pen_id: string; date: string; state: string; opening: boolean; details: { occupation_id: string; category: string; quality: string; expected: number; observed: number; difference: number }[] }
export interface CuyAlert { id: string; pen_id: string; kind: string; text: string; resolved_at: string | null }
export interface Daily { id: string; shed_id: string; date: string; state: string; closed_at: string | null; revisions: { action: string; reason: string; registered_at: string }[] }
export interface Ledger { id: string; kind: string; date: string; registered_at: string; actor: string; reason: string; metadata: Record<string, unknown>; lines: { category: string; quality: string; delta: number; snapshot: { pen_id: string; pen: string; lot_id: string; center: string; shed: string } }[] }
export interface Dashboard { updated_at: string; population: number; in_transit: number; pens: Pen[]; alerts: CuyAlert[]; indicators: { pen: string; live: number; stillborn: number; mortality: number; weaned: number; average_females: number | null; weaned_per_female: number | null; status: string }[] }
export const purposes: Record<string, string> = { MATERNIDAD: 'Empadre / Maternidad', RECRIA_MACHOS: 'Recría Machos', RECRIA_HEMBRAS: 'Recría Hembras', ACABADO: 'Venta / Acabado', ENFERMERIA: 'Enfermería / Descarte' }
export function categoriesForPurpose(purpose?: string): Category[] {
  if (purpose === 'RECRIA_MACHOS') return ['MACHO']
  if (purpose === 'RECRIA_HEMBRAS') return ['HEMBRA']
  if (purpose === 'ACABADO') return ['MACHO', 'HEMBRA']
  return ['MACHO', 'HEMBRA', 'LACTANTE']
}
export function limaToday() { return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()) }
