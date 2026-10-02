import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, apiMode } from '../api/client'
import type { Page } from '../api/types'
import { useAuth } from '../auth/AuthProvider'
import { Button, Notice } from '../components/ui'
import type { Production } from './ProductionRevision'

export function ProductionHistory() {
  const { account } = useAuth()
  const query = useQuery({ queryKey: ['milkings', account?.id], queryFn: () => api.request<Page<Production>>('/milkings'), enabled: !!account && navigator.onLine })
  return <section className="stack"><h1>Historial de producción</h1>
    {apiMode === 'mock' && <Notice tone="warning">Solo producción de demostración; no incluye registros reales.</Notice>}
    {query.isPending && <Notice>Cargando historial…</Notice>}
    {query.isError && <Notice tone="error">No pudimos consultar producción. <Button variant="secondary" onClick={() => void query.refetch()}>Reintentar</Button></Notice>}
    {query.data?.results.map(item => <article className="card" key={item.id}><h2>{item.date} · {item.shift_name}</h2><p>{item.total_litres} L · {item.state}</p><Link to={`/producciones/${item.id}`}>Ver detalle y correcciones</Link></article>)}
    {query.data?.results.length === 0 && <p>No hay producciones documentadas.</p>}
    {query.data?.next && <Notice>Hay más producciones; falta paginación B27.</Notice>}
  </section>
}
