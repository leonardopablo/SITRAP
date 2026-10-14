import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, apiMode } from '../api/client'
import type { Page } from '../api/types'
import { useAuth } from '../auth/AuthProvider'
import { Notice } from '../components/ui'

interface DraftTransfer {
  id: string
  code: string
  state: string
  units_presentation: number
  capabilities: string[]
  current_version?: { lines?: { lot_id: string }[] }
  lot_code?: string
  lot_date?: string
}

interface LotSummary { id: string; code: string; date: string }

const displayDate = (value?: string) => value ? value.split('-').reverse().join('/') : 'fecha no disponible'

export function PendingTransferDrafts() {
  const { account } = useAuth()
  const query = useQuery({
    queryKey: ['pending-transfer-drafts', account?.id],
    queryFn: async () => {
      const [transfers, lots] = await Promise.all([
        api.request<Page<DraftTransfer>>(apiMode === 'http' ? '/transfers?state=BORRADOR&limit=100' : '/transfers'),
        api.request<Page<LotSummary>>(apiMode === 'http' ? '/lots?limit=100' : '/lots'),
      ])
      const byId = new Map(lots.results.map(lot => [lot.id, lot]))
      return transfers.results
        .filter(item => item.state === 'BORRADOR' && item.capabilities?.includes('send'))
        .map(item => {
          const lot = byId.get(item.current_version?.lines?.[0]?.lot_id ?? '')
          return { ...item, lot_code: lot?.code, lot_date: lot?.date }
        })
        .sort((left, right) => (right.lot_date ?? '').localeCompare(left.lot_date ?? '') || left.code.localeCompare(right.code))
    },
    enabled: !!account && navigator.onLine,
  })
  const drafts = query.data ?? []
  const newestDate = drafts[0]?.lot_date
  const current = drafts.filter(item => item.lot_date === newestDate)
  const previous = drafts.filter(item => item.lot_date !== newestDate)
  const card = (item: DraftTransfer) => <article className="card pending-transfer-card" key={item.id}>
    <div><strong>Lote del {displayDate(item.lot_date)}</strong><p>{item.units_presentation} bolsas · todavía no se notificó al conductor</p><span className="help">{item.lot_code ?? item.code}</span></div>
    <Link className="button" to={`/entregas/${item.id}`}>Revisar y enviar</Link>
  </article>
  return <section className="stack pending-transfer-drafts" aria-labelledby="pending-transfer-title">
    <div className="row"><h2 id="pending-transfer-title">Entregas pendientes de enviar</h2>{drafts.length > 0 && <span className="badge">{drafts.length}</span>}</div>
    {query.isPending && <Notice>Buscando borradores de entrega…</Notice>}
    {query.isError && <Notice tone="warning">No pudimos consultar los borradores. Comprueba la conexión y vuelve a intentarlo.</Notice>}
    {!query.isPending && !query.isError && drafts.length === 0 && <p>No tienes borradores pendientes de enviar.</p>}
    {current.map(card)}
    {previous.length > 0 && <details className="card pending-transfer-previous"><summary>Borradores anteriores ({previous.length})</summary><div className="stack">{previous.map(card)}</div></details>}
  </section>
}
