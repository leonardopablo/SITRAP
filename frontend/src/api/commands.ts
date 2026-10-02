import type { Command, CommandType } from './types'

/** Executable policy from 04 §5, not a separate business specification. */
export const onlineOnly = new Set<CommandType>(['MILKING_RECTIFY', 'MILKING_VOID', 'TRANSFER_REVISE', 'TRANSFER_CANCEL', 'CORRECTION_CREATE', 'CORRECTION_WITHDRAW'])
export const downloadedOnly = new Set<CommandType>(['TRANSFER_PICKUP', 'TRANSFER_RECEIVE', 'CORRECTION_ACCEPT', 'CORRECTION_REJECT'])
export function createCommand(input: Omit<Command, 'event_id' | 'occurred_at' | 'depends_on'> & { depends_on?: string[] }): Command {
  const snapshot = structuredClone(input)
  return { ...snapshot, event_id: crypto.randomUUID(), occurred_at: new Date().toISOString(), depends_on: snapshot.depends_on ?? [] }
}
export function commandPath(command: Command): string {
  const id = encodeURIComponent(command.entity_id)
  const paths: Record<CommandType, string> = {
    MILKING_CREATE: '/milkings', MILKING_UPDATE: `/milkings/${id}`, MILKING_CONFIRM: `/milkings/${id}/confirm`, MILKING_RECTIFY: `/milkings/${id}/rectify`, MILKING_VOID: `/milkings/${id}/void`,
    TRANSFER_CREATE: '/transfers', TRANSFER_UPDATE: `/transfers/${id}`, TRANSFER_SEND: `/transfers/${id}/send`, TRANSFER_REVISE: `/transfers/${id}/revise`, TRANSFER_CANCEL: `/transfers/${id}/cancel`, TRANSFER_PICKUP: `/transfers/${id}/pickup`, TRANSFER_RECEIVE: `/transfers/${id}/receive`,
    CORRECTION_CREATE: `/transfers/${id}/corrections`, CORRECTION_ACCEPT: `/corrections/${id}/accept`, CORRECTION_REJECT: `/corrections/${id}/reject`, CORRECTION_WITHDRAW: `/corrections/${id}/withdraw`,
  }
  return paths[command.type]
}
