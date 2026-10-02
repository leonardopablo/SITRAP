import { api } from '../api/client'
import { getDevice } from '../offline/db'

export interface PushConfig { enabled: boolean; vapid_public_key: string | null }
export interface PushRecord { id: string; device_id: string; endpoint: string; active: boolean }
export function pushSupported() { return typeof window !== 'undefined' && 'Notification' in window && 'serviceWorker' in navigator && 'PushManager' in window }
export function vapidBytes(key: string): Uint8Array<ArrayBuffer> {
  const input = key.replace(/-/g, '+').replace(/_/g, '/')
  const binary = atob(input.padEnd(Math.ceil(input.length / 4) * 4, '='))
  const bytes = new Uint8Array(new ArrayBuffer(binary.length))
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes
}
export async function subscribePhone(accountId: string, key: string): Promise<PushRecord> {
  if (!pushSupported()) throw new Error('Este navegador no admite avisos del teléfono.')
  if (!navigator.onLine) throw new Error('Conéctate para activar avisos.')
  // Must be invoked from explicit button handler; never on page load.
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') throw new Error('Permiso denegado. Puedes seguir usando los avisos dentro de SITRAP.')
  const registration = await navigator.serviceWorker.ready
  const device = await getDevice(accountId)
  if (!device.registered) throw new Error('Prepara el dispositivo antes de activar avisos.')
  const existing = await registration.pushManager.getSubscription()
  const subscription = existing ?? await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: vapidBytes(key) })
  const json = subscription.toJSON()
  if (!subscription.endpoint || !json.keys?.p256dh || !json.keys.auth) throw new Error('No se pudo obtener una suscripción válida.')
  try { return await api.post<PushRecord>('/push/subscriptions', { device_id: device.device_id, endpoint: subscription.endpoint, p256dh: json.keys.p256dh, auth: json.keys.auth }) }
  catch (error) { if (!existing) await subscription.unsubscribe(); throw error }
}
export async function unsubscribePhone(id: string) {
  await api.request(`/push/subscriptions/${encodeURIComponent(id)}`, { method: 'DELETE' })
  const registration = await navigator.serviceWorker.ready
  await (await registration.pushManager.getSubscription())?.unsubscribe()
}
export async function unsubscribeBrowserOnLogout() {
  if (!pushSupported()) return
  const registration = await navigator.serviceWorker.ready
  await (await registration.pushManager.getSubscription())?.unsubscribe()
}
