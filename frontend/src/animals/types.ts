/** Provisional B12 DTO. No lactation state in MVP. */
export interface Animal { id: string; code: string; name: string | null; species_id: string; sex: 'HEMBRA' | 'MACHO'; status: 'ACTIVO' | 'INACTIVO'; center_id: string; center_name: string }
