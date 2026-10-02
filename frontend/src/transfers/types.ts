export interface Lot { id: string; code: string; center_id: string; product_id: string; produced_litres: string; unlinked_litres: string; confirmed: boolean }
export interface Option { id: string; name: string }
export interface AssignmentOptions { destinations: Option[]; drivers: Option[]; receivers: Option[]; defaults?: { destination_id?: string; driver_id?: string; receiver_id?: string } }
export interface Presentation { id: string; product_id: string; name: string; content_base: string; admits_fraction: boolean; active: boolean }
