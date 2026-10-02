import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, apiMode } from '../api/client'
import type { Page } from '../api/types'
import { useAuth } from '../auth/AuthProvider'
import { useConnection } from '../offline/SyncPanel'
import { Button, Notice } from '../components/ui'
import type { Correction } from './CorrectionPage'

export function CorrectionHistory() {
  const { account } = useAuth()
  const online = useConnection()
  const query = useQuery({ queryKey: ['corrections', account?.id], queryFn: () => api.request<Page<Correction>>('/corrections'), enabled: !!account && online })
  return <section className="stack"><h1>Correcciones</h1>
    {apiMode === 'mock' && <Notice tone="warning">Historial de demostración, solo en memoria. No equivale a decisiones reales.</Notice>}
    {query.isPending && <Notice>Cargando propuestas…</Notice>}
    {query.isError && <Notice tone="error">No pudimos consultar propuestas. <Button variant="secondary" onClick={() => void query.refetch()}>Reintentar</Button></Notice>}
    {query.data?.results.length === 0 && <p>No hay solicitudes de corrección descargadas.</p>}
    {query.data?.results.map(item => <article className="card" key={item.id}><h2>Entrega {item.transfer_id}</h2><p>{item.original_quantity} L → {item.proposed_quantity} L · {item.state}</p><p>Transporte: {item.decisions.some(decision => decision.role === 'TRANSPORTE') ? 'Respondió' : 'Pendiente'} · Recepción: {item.decisions.some(decision => decision.role === 'RECEPCION') ? 'Respondió' : 'Pendiente'}</p><Link to={`/correcciones/${item.id}`}>Ver historial y propuesta</Link></article>)}
    {query.data?.next && <Notice>Hay más resultados. La paginación se conectará con el contrato B25.</Notice>}
  </section>
}
