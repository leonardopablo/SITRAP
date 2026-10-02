/** Provisional read DTO (04 §6); verify against B18 OpenAPI. */
export interface Notification { id: string; type: string; title: string; text: string; created_at: string; read_at: string | null; entity_type: 'transfer' | 'correction'; entity_id: string; version_id: string | null }
export interface Inbox { results: Notification[]; next: string | null; count: number; unread_count: number }
