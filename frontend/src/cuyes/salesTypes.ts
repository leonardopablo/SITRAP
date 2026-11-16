import type { Bucket } from './types'
import type { components as Backend } from '../api/backend.generated'
export type SaleType = Backend['schemas']['SaleCommandRequest']['type']
export const saleTypes = ['SALE_CREATE', 'SALE_CONFIRM', 'SALE_REJECT', 'SALE_PROPOSE', 'SALE_PROPOSAL_REVIEW', 'SALE_PAY', 'SALE_DRIVER', 'SALE_SELECT', 'SALE_ORIGIN', 'SALE_PICKUP', 'SALE_DEPART', 'SALE_ARRIVE', 'SALE_COLLECT', 'SALE_CANCEL', 'SALE_WEIGH', 'SALE_FINANCE', 'SALE_RESOLVE_STOCK'] as const satisfies readonly SaleType[]
export interface Module { id: string; name: string; active: boolean; components: { category: string; quality: string; quantity: number }[] }
export interface SaleLine { id: string; kind: 'UNIDAD' | 'PESO' | 'MODULO'; units: number; animal_count: number; recipe: { category: string; quality: string; quantity: number }[]; category: string; quality: string; module_id: string | null; weight_kg: string | null; weight_basis: string; billing_unit: string; unit_price?: string; total?: string }
export interface Selection { line_id: string; occupation_id: string; category: string; quality: string; quantity: number; pen?: string; shed_id?: string }
export interface Candidate { occupation_id: string; lot_id: string; pen_id: string; pen: string; shed_id: string; category: string; quality: string; available: number; opened_on: string }
export interface Sale { id: string; code: string; center_id: string; center: string; mode: 'DIRECTO' | 'PUNTO'; point: { id: string; name: string } | null; driver: { id: string; name: string } | null; state: string; display_state: string; stage: number; version: number; shortage: boolean; financial_hold: boolean; client: { name: string; contact?: string; reference?: string }; total?: string; currency?: string; approved_total?: string; lines: SaleLine[]; actions: string[]; updated_at: string; reservation: { id: string; state: string; expires_at: string; details: Bucket[]; consumed_at: string | null } | null; preparation: { id: string; round: number; items: Selection[]; other_allocations: Selection[]; conformities: { stage: string; shed_id: string | null; actor_id: string; registered_at: string }[] } | null; dispatch: { id: string; movement_id: string; departed_at: string; details: { category: string; quality: string; quantity: number; snapshot: Record<string, unknown> }[] } | null; deliveries: { stage: string; registered_by_id: string; physical_responsible: string; reference: string; registered_at: string }[]; payment?: { amount: string; currency: string; method: string; reference: string; evidence_id: string; validated_at: string } | null; proposals?: { id: string; state: string; reason: string; items: unknown }[]; financial_reviews?: { id: string; difference: string; treatment: string; reason: string; reference: string }[] }
export interface SalesOptions { centers: { id: string; name: string }[]; points: { id: string; name: string }[]; drivers: { id: string; name: string; center_ids: string[] }[] }
export interface Availability { referential: boolean; scope: string; buckets: { category: string; quality: string; available: number }[]; modules: (Module & { offerable: number })[] }

// Optional read fields: the server omits administrative details in operator views.
export interface Sale {
  reason?: string
  manager?: { id: string; name: string }
  ready_to_dispatch: boolean
  reservation_history?: { id: string; state: string; created_at: string; expires_at: string; released_at: string | null; consumed_at: string | null }[]
}
