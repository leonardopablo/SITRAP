import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useLiveQuery } from 'dexie-react-hooks'
import { api, apiMode } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { useWorkspace } from '../auth/workspace'
import { listEvents } from '../offline/db'
import { useConnection } from '../offline/SyncPanel'
import { Button, Notice } from '../components/ui'

export function PdfDeliveries() {
  const { account } = useAuth()
  const { assignment } = useWorkspace()
  const online = useConnection()
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [warning, setWarning] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const count = useLiveQuery(async () => account ? (await listEvents(account.id)).filter(event => event.status !== 'APLICADA').length : 0, [account?.id], 0)
  const role = assignment?.role
  const report = role === 'RECEPCION' ? 'receptions' : 'transfers'
  const title = role === 'RECEPCION' ? 'PDF de recepciones' : 'PDF de transporte'
  const valid = /^\d{4}-\d{2}-\d{2}$/.test(from) && /^\d{4}-\d{2}-\d{2}$/.test(to) && from <= to
  async function download() {
    if (!valid || !online || apiMode !== 'http' || busy || !['RECEPCION', 'TRANSPORTE'].includes(role ?? '')) return
    setBusy(true); setError('')
    try {
      const query = new URLSearchParams({ from, to })
      const blob = await api.pdf(`/reports/${report}.pdf?${query}`)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a'); link.href = url; link.download = `sitrap-${report}-${from}-${to}.pdf`; link.click()
      setTimeout(() => URL.revokeObjectURL(url), 60000)
      setWarning(false)
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  return <section className="stack form"><h1>{title}</h1>
    <p>Solo incluye entregas sincronizadas hasta el corte del servidor. El servidor comprueba el ámbito de la cuenta.</p>
    {apiMode === 'mock' && <Notice tone="warning">La API de PDF no está disponible en el mock. No se mostrará una exportación local como informe oficial.</Notice>}
    <div className="row"><div className="field"><label htmlFor="delivery-pdf-from">Desde</label><input type="date" id="delivery-pdf-from" value={from} onChange={event => setFrom(event.target.value)} /></div><div className="field"><label htmlFor="delivery-pdf-to">Hasta</label><input type="date" id="delivery-pdf-to" value={to} onChange={event => setTo(event.target.value)} /></div></div>
    {!valid && (from || to) && <Notice tone="error">Elige un período válido.</Notice>}
    {error && <Notice tone="error">{error}</Notice>}
    <Button disabled={!valid || !online || apiMode !== 'http'} busy={busy} onClick={() => count > 0 ? setWarning(true) : void download()}>Descargar {title.toLowerCase()}</Button>
    {warning && <Notice tone="warning">Este informe incluye solo lo sincronizado; tienes {count} operaciones no aceptadas en este teléfono. <Link to="/sincronizacion">Sincronizar primero</Link> o <Button variant="secondary" onClick={() => void download()}>Descargar de todos modos</Button>.</Notice>}
  </section>
}
