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
}

export function PendingTransferDrafts() {
  const { account } = useAuth()
  const query = useQuery({
    queryKey: ['pending-transfer-drafts', account?.id],
    queryFn: () => api.request<Page<DraftTransfer>>(apiMode === 'http' ? '/transfers?state=BORRADOR&limit=100' : '/transfers'),
    enabled: !!account && navigator.onLine,
  })
  const drafts = query.data?.results.filter(item => item.state === 'BORRADOR' && item.capabilities?.includes('send')) ?? []
  return <section className="stack pending-transfer-drafts" aria-labelledby="pending-transfer-title">
    <div className="row"><h2 id="pending-transfer-title">Entregas pendientes de enviar</h2>{drafts.length > 0 && <span className="badge">{drafts.length}</span>}</div>
    {query.isPending && <Notice>Buscando borradores de entrega…</Notice>}
    {query.isError && <Notice tone="warning">No pudimos consultar los borradores. Comprueba la conexión y vuelve a intentarlo.</Notice>}
    {!query.isPending && !query.isError && drafts.length === 0 && <p>No tienes borradores pendientes de enviar.</p>}
    {drafts.map(item => <article className="card pending-transfer-card" key={item.id}>
      <div><strong>{item.code}</strong><p>{item.units_presentation} bolsas · todavía no se notificó al conductor</p></div>
      <Link className="button" to={`/entregas/${item.id}`}>Revisar y enviar</Link>
    </article>)}
  </section>
}
