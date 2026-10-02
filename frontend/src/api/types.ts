/** Provisional contract from SITRAP_04. Replace/validate against B39 OpenAPI. */
export type Role = 'PRODUCCION' | 'TRANSPORTE' | 'RECEPCION' | 'ADMIN'
export interface Assignment { id: string; role: Role; location_id: string | null; location_name: string; scope: 'GLOBAL' | 'UBICACION' }
export interface Account { id: string; username: string; name: string; change_password_required: boolean; assignments: Assignment[]; capabilities: string[] }
export interface ErrorBody { code: string; message: string; field_errors?: Record<string, string[]>; retryable: boolean }
