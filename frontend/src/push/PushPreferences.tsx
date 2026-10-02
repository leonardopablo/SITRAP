import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthProvider'
import { api, apiMode } from '../api/client'
import { Button, Notice } from '../components/ui'
import { useConnection } from '../offline/SyncPanel'
import { pushSupported, subscribePhone, unsubscribePhone, type PushConfig, type PushRecord } from './subscription'

export function PushPreferences() {
  const { account } = useAuth()
  const online = useConnection()
  const cache = useQueryClient()
  const [dismissed, setDismissed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const config = useQuery({ queryKey: ['push-config', account?.id], queryFn: () => api.request<PushConfig>('/push/config'), enabled: !!account && online })
  const records = useQuery({ queryKey: ['push-records', account?.id], queryFn: () => api.request<{ results: PushRecord[] }>('/push/subscriptions'), enabled: !!account && online })
  const [subscription, setSubscription] = useState<PushSubscription | null>(null)
  useEffect(() => { if (pushSupported()) void navigator.serviceWorker.ready.then(reg => reg.pushManager.getSubscription()).then(setSubscription).catch(() => setSubscription(null)) }, [account?.id])
  const active = records.data?.results.find(item => item.active && !!subscription && item.endpoint === subscription.endpoint)
  async function enable() {
    if (!account || !config.data?.vapid_public_key || busy) return
    setBusy(true); setError(''); setMessage('')
    try { await subscribePhone(account.id, config.data.vapid_public_key); await cache.invalidateQueries({ queryKey: ['push-records', account.id] }); setSubscription(await (await navigator.serviceWorker.ready).pushManager.getSubscription()); setMessage('Suscripción guardada en el sistema. El teléfono puede recibir avisos cuando red y navegador lo permitan.') }
    catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  async function disable(id: string) {
    setBusy(true); setError(''); setMessage('')
    try { await unsubscribePhone(id); await cache.invalidateQueries({ queryKey: ['push-records', account?.id] }); setSubscription(null); setMessage('Suscripción desactivada. Consulta tus avisos dentro de SITRAP.') }
    catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }
  return <section className="card stack form"><h1>Notificaciones del teléfono</h1>
    {apiMode === 'mock' && <Notice tone="warning">Modo simulado: no se solicita permiso ni se registra una suscripción push. La bandeja interna sigue disponible.</Notice>}
    <p>Los avisos del teléfono son opcionales y no sustituyen el estado dentro de SITRAP. El permiso se solicita solo al pulsar Activar.</p>
    {!pushSupported() && <Notice tone="warning">Este navegador no admite Web Push. Consulta tus avisos dentro de SITRAP.</Notice>}
    {!online && <Notice tone="warning">Conéctate para activar o desactivar los avisos. La bandeja interna sigue disponible.</Notice>}
    {config.isError || records.isError ? <Notice tone="error">No se pudo consultar la configuración actual. No declaramos activación completa.</Notice> : null}
    {config.isPending && online && <Notice>Comprobando compatibilidad…</Notice>}
    {config.data && !config.data.enabled && <Notice>Push no está configurado en el servidor. Consulta tus avisos dentro de SITRAP.</Notice>}
    {active && <Notice tone="success">Avisos del teléfono activados para este dispositivo. No garantizan entrega inmediata ni lectura.</Notice>}
    {subscription && !active && <Notice tone="warning">Hay una suscripción del navegador sin vinculación verificada con esta cuenta. No está activada para ti; puedes registrarla explícitamente con Activar.</Notice>}
    {typeof Notification !== 'undefined' && Notification.permission === 'denied' && <Notice tone="warning">Permiso rechazado. Si cambias de opinión, revisa los permisos del sitio en el navegador.</Notice>}
    {error && <Notice tone="error">{error}</Notice>}{message && <Notice>{message}</Notice>}
    {!active && !dismissed && pushSupported() && config.data?.enabled && apiMode === 'http' && <div className="row"><Button busy={busy} disabled={!online || !config.data.vapid_public_key} onClick={() => void enable()}>Activar notificaciones</Button><Button variant="secondary" onClick={() => setDismissed(true)}>Ahora no</Button></div>}
    {active && <Button variant="secondary" busy={busy} disabled={!online} onClick={() => void disable(active.id)}>Desactivar notificaciones</Button>}
  </section>
}
