import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useLiveQuery } from 'dexie-react-hooks'
import { api, apiMode } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { useWorkspace } from '../auth/workspace'
import { listEvents } from '../offline/db'
import { useConnection } from '../offline/SyncPanel'
import { Button, Notice } from '../components/ui'

export function PdfProduction() {
  const { account } = useAuth()
  const { assignment } = useWorkspace()
  const online = useConnection()
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState(false)
  const pending = useLiveQuery(async () => account ? (await listEvents(account.id)).filter(item => item.status !== 'APLICADA').length : 0, [account?.id], 0)
  const valid = /^\d{4}-\d{2}-\d{2}$/.test(from) && /^\d{4}-\d{2}-\d{2}$/.test(to) && from <= to
  async function download() {
    if (!valid || !online || apiMode !== 'http' || busy) return
    setBusy(true); setError('')
    try {
      const params = new URLSearchParams({ from, to, ...(assignment?.location_id ? { center_id: assignment.location_id } : {}) })
      const blob = await api.pdf(`/reports/production.pdf?${params}`)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = `sitrap-produccion-${from}-${to}.pdf`; anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 60000)
      setWarning(false)
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  return <section className="stack form"><h1>PDF de producción</h1>
    <p>El servidor genera un informe de datos sincronizados con corte y filtros. No se crea un PDF definitivo desde los datos del teléfono.</p>
    {apiMode === 'mock' && <Notice tone="warning">No hay API de informes conectada. Descarga deshabilitada; no se fabricará un PDF de demostración.</Notice>}
    <div className="row"><div className="field"><label htmlFor="pdf-prod-from">Desde</label><input type="date" id="pdf-prod-from" value={from} onChange={event => setFrom(event.target.value)} /></div><div className="field"><label htmlFor="pdf-prod-to">Hasta</label><input type="date" id="pdf-prod-to" value={to} onChange={event => setTo(event.target.value)} /></div></div>
    {!valid && (from || to) && <Notice tone="error">Elige fechas válidas en orden.</Notice>}
    {!online && <Notice tone="warning">Descargar requiere conexión.</Notice>}
    {error && <Notice tone="error">{error}</Notice>}
    <Button disabled={!valid || !online || apiMode !== 'http'} busy={busy} onClick={() => { if (pending > 0) setWarning(true); else void download() }}>Descargar producción</Button>
    {warning && <Notice tone="warning">Este informe incluye solo lo sincronizado; tienes {pending} operaciones no aceptadas en este teléfono. <Link to="/sincronizacion">Sincronizar primero</Link> o <Button variant="secondary" onClick={() => void download()}>Descargar de todos modos</Button>.</Notice>}
  </section>
}
