import 'fake-indexeddb/auto'
import Dexie from 'dexie'
import { saveCopy, SitrapDB } from './db'
import { linkFieldNote, listFieldNotes, saveFieldNote } from './notes'

it('migra base v1 y preserva eventos, notas por cuenta y vínculo local sin firmas', async () => {
  const name = `notes-${crypto.randomUUID()}`
  const old = new Dexie(name)
  old.version(1).stores({ events: 'event_id, account_id, [account_id+status], created_at', copies: 'key, account_id, [account_id+kind], [account_id+entity_id]', devices: 'account_id' })
  await old.table('events').put({ account_id: 'one', device_id: 'd', event_id: crypto.randomUUID(), command: {}, status: 'PENDIENTE', created_at: '', updated_at: '' })
  old.close()
  const store = new SitrapDB(name)
  const note = await saveFieldNote('one', '  Llegué al centro sin señal  ', store)
  expect((await listFieldNotes('one', store))[0].text).toBe('Llegué al centro sin señal')
  expect(await listFieldNotes('two', store)).toEqual([])
  expect(await store.events.count()).toBe(1)
  await expect(linkFieldNote('one', note.id, 'transfer-1', store)).rejects.toThrow('Descarga')
  await saveCopy('two', 'transfer', 'transfer-1', { code: 'Otro' }, store)
  await expect(linkFieldNote('one', note.id, 'transfer-1', store)).rejects.toThrow('Descarga')
  await saveCopy('one', 'transfer', 'transfer-1', { code: 'Documento autorizado' }, store)
  await linkFieldNote('one', note.id, 'transfer-1', store)
  await expect(linkFieldNote('one', note.id, 'transfer-2', store)).rejects.toThrow('no disponible')
  expect(await store.events.count()).toBe(1)
  store.close(); await store.delete()
})
