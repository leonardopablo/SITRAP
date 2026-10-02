import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useLiveQuery } from 'dexie-react-hooks'
import { useAuth } from '../auth/AuthProvider'
import { db } from './db'
import { linkFieldNote, listFieldNotes, saveFieldNote } from './notes'
import { Button, Notice } from '../components/ui'

export function FieldNotes() {
  const { account } = useAuth()
  const [text, setText] = useState('')
  const [chosen, setChosen] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const notes = useLiveQuery(() => account ? listFieldNotes(account.id) : [], [account?.id], [])
  const transfers = useLiveQuery(() => account ? db.copies.where('[account_id+kind]').equals([account.id, 'transfer']).toArray() : [], [account?.id], [])
  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true); setError(''); setMessage('')
    try { await action(); setMessage(success) } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  return <section className="stack form"><h1>Notas provisionales de campo</h1>
    <Notice tone="warning">Solo en este teléfono y esta cuenta. Una nota no es una solicitud, recogida, firma ni cantidad oficial. No se sincroniza como comando y no genera un lote.</Notice>
    <div className="field"><label htmlFor="field-note">Anotación sin datos sensibles</label><textarea id="field-note" maxLength={1000} value={text} onChange={event => setText(event.target.value)} /></div>
    <Button busy={busy} disabled={!text.trim()} onClick={() => void run(async () => { await saveFieldNote(account!.id, text); setText('') }, 'Nota guardada solo en este teléfono.')}>Guardar nota provisional</Button>
    {error && <Notice tone="error">{error}</Notice>}{message && <Notice>{message}</Notice>}
    {!notes.length && <p>No hay notas locales.</p>}
    {notes.map(note => <article className="card stack" key={note.id}><h2>Nota · {new Intl.DateTimeFormat('es-PE', { dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Lima' }).format(new Date(note.created_at))}</h2><p>{note.text}</p>
      {note.linked_transfer_id ? <p>Referencia local: <Link to={`/entregas/${note.linked_transfer_id}`}>entrega vinculada</Link>. No confirma ni modifica la entrega.</p> : <><div className="field"><label htmlFor={`link-${note.id}`}>Relacionar con entrega descargada</label><select id={`link-${note.id}`} value={chosen[note.id] ?? ''} onChange={event => setChosen(previous => ({ ...previous, [note.id]: event.target.value }))}><option value="">Selecciona entrega</option>{transfers.map(copy => <option key={copy.key} value={copy.entity_id}>{(copy.document as { code?: string })?.code ?? copy.entity_id}</option>)}</select></div>
        <Button variant="secondary" busy={busy} disabled={!chosen[note.id]} onClick={() => void run(() => linkFieldNote(account!.id, note.id, chosen[note.id]), 'Nota relacionada localmente. Revisa el documento actual antes de cualquier confirmación.')}>Vincular solo como referencia</Button></>}
    </article>)}
  </section>
}
