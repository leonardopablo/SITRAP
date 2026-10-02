import { db, type FieldNote, type SitrapDB } from './db'

export async function saveFieldNote(accountId: string, text: string, store: SitrapDB = db): Promise<FieldNote> {
  if (!accountId || !text.trim() || text.trim().length > 1000) throw new Error('Escribe una nota de hasta 1000 caracteres.')
  const note: FieldNote = { id: crypto.randomUUID(), account_id: accountId, text: text.trim(), created_at: new Date().toISOString() }
  await store.notes.add(note)
  return note
}
export function listFieldNotes(accountId: string, store: SitrapDB = db) {
  return store.notes.where('account_id').equals(accountId).sortBy('created_at')
}
/** Link for human review only: never enqueue, sign or alter the server document. */
export async function linkFieldNote(accountId: string, noteId: string, transferId: string, store: SitrapDB = db) {
  return store.transaction('rw', store.notes, store.copies, async () => {
    const note = await store.notes.get(noteId)
    if (!note || note.account_id !== accountId || note.linked_transfer_id) throw new Error('Nota no disponible para vincular.')
    const copy = await store.copies.get(JSON.stringify([accountId, 'transfer', transferId]))
    if (!copy) throw new Error('Descarga una entrega autorizada antes de vincular la nota.')
    await store.notes.update(noteId, { linked_transfer_id: transferId, linked_at: new Date().toISOString() })
  })
}
