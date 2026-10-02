import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { Button, Notice } from '../components/ui'
import { Illustration } from '../components/Illustration'
import { useConnection } from '../offline/SyncPanel'
import type { Inbox, Notification } from './types'

const queryKey = (accountId: string) => ['inbox', accountId]
function useInbox() {
  const { account } = useAuth()
  const online = useConnection()
  return useQuery({ queryKey: queryKey(account?.id ?? ''), queryFn: () => api.request<Inbox>('/notifications'), enabled: online && !!account,
    refetchInterval: () => document.visibilityState === 'visible' && navigator.onLine ? 10000 : false,
    refetchOnWindowFocus: true, retry: 1 })
}
export function useInboxRefresh() {
  const { account } = useAuth()
  const cache = useQueryClient()
  useEffect(() => {
    if (!account) return
    const refresh = () => { if (navigator.onLine && document.visibilityState === 'visible') void cache.invalidateQueries({ queryKey: queryKey(account.id) }) }
    document.addEventListener('visibilitychange', refresh)
    window.addEventListener('online', refresh)
    navigator.serviceWorker?.addEventListener('message', refresh)
    return () => { document.removeEventListener('visibilitychange', refresh); window.removeEventListener('online', refresh); navigator.serviceWorker?.removeEventListener('message', refresh) }
  }, [account?.id, cache])
}
export function InboxBell() {
  const { data, isError } = useInbox()
  useInboxRefresh()
  return <Link to="/avisos" aria-label={`Avisos${data ? `, ${data.unread_count} no leídos` : ''}`}>Avisos {data ? `(${data.unread_count})` : isError ? '(!)' : '(…)'} </Link>
}
function destination(item: Notification) { return item.entity_type === 'correction' ? `/correcciones/${encodeURIComponent(item.entity_id)}` : `/entregas/${encodeURIComponent(item.entity_id)}` }
export function InboxPage() {
  const { account } = useAuth()
  const online = useConnection()
  const cache = useQueryClient()
  const { data, isPending, isError, dataUpdatedAt, refetch } = useInbox()
  const [onlyUnread, setOnlyUnread] = useState(false)
  const [actionError, setActionError] = useState('')
  const [reading, setReading] = useState<string | null>(null)
  const list = data?.results.filter(item => !onlyUnread || !item.read_at) ?? []
  async function markRead(id: string) {
    setReading(id); setActionError('')
    try { await api.post(`/notifications/${encodeURIComponent(id)}/read`); await cache.invalidateQueries({ queryKey: queryKey(account!.id) }) }
    catch (error) { setActionError((error as Error).message) }
    finally { setReading(null) }
  }
  return <section className="stack"><h1>Avisos</h1>
    <p>Leer un aviso no confirma una recogida, recepción ni corrección.</p>
    {dataUpdatedAt > 0 && <p className="help">Última actualización: {new Intl.DateTimeFormat('es-PE', { dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Lima' }).format(new Date(dataUpdatedAt))}</p>}
    <div className="row"><Button variant={!onlyUnread ? 'primary' : 'secondary'} aria-pressed={!onlyUnread} onClick={() => setOnlyUnread(false)}>Todos</Button><Button variant={onlyUnread ? 'primary' : 'secondary'} aria-pressed={onlyUnread} onClick={() => setOnlyUnread(true)}>No leídos</Button><Button variant="secondary" disabled={!online} onClick={() => void refetch()}>Actualizar</Button></div>
    {isPending && <Notice>Cargando avisos…</Notice>}
    {isError && <Notice tone="error">No pudimos actualizar los avisos. Reintenta con conexión.</Notice>}
    {!isPending && !isError && list.length === 0 && <div className="card"><Illustration kind="empty" /><p>{onlyUnread ? 'No tienes avisos sin leer.' : 'No tienes avisos por ahora.'}</p></div>}
    {actionError && <Notice tone="error">{actionError}</Notice>}
    {list.map(item => <article className="card stack" key={item.id}><div className="row"><strong>{item.title}</strong><span className="badge">{item.read_at ? 'Leído' : 'No leído'}</span></div><p>{item.text}</p>
      <p className="help">{new Intl.DateTimeFormat('es-PE', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Lima' }).format(new Date(item.created_at))}</p>
      <div className="row"><Link className="button secondary" to={destination(item)}>{item.entity_type === 'correction' ? 'Ver corrección' : 'Ver entrega'}</Link>
      {!item.read_at && <Button disabled={!online} busy={reading === item.id} onClick={() => void markRead(item.id)}>Marcar leído</Button>}</div>
    </article>)}
    {data?.next && <Notice>Hay más avisos. La paginación completa se conectará cuando esté disponible B18/OpenAPI.</Notice>}
  </section>
}
