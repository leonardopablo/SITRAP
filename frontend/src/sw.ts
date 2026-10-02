/// <reference lib="webworker" />
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'
import { safePushRoute, safeTag } from './push/route'

declare const self: ServiceWorkerGlobalScope & { __WB_MANIFEST: Array<{ url: string; revision: string | null }> }
precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()
// Only public application assets: authenticated API responses are never cached by SW.
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html'), { denylist: [/^\/api\//] }))
// Updates wait for explicit acceptance. Outbox persists independently in IndexedDB.
self.addEventListener('message', event => { if (event.data?.type === 'SKIP_WAITING') void self.skipWaiting() })
// Push only refreshes read-only views; never execute a business command here.
self.addEventListener('push', event => {
  event.waitUntil((async () => {
    let payload: { notification_id?: unknown; route?: unknown } = {}
    try { payload = event.data?.json() ?? {} } catch { /* malformed payload opens inbox */ }
    const route = safePushRoute(payload.route)
    await self.registration.showNotification('SITRAP', { body: 'Tienes un aviso pendiente en SITRAP. Abre la aplicación para ver el estado actual.', tag: safeTag(payload.notification_id), data: { route } })
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    windows.forEach(window => window.postMessage({ type: 'SITRAP_PUSH_REFRESH' }))
  })())
})
self.addEventListener('notificationclick', event => {
  event.notification.close()
  event.waitUntil((async () => {
    const route = safePushRoute((event.notification.data as { route?: unknown } | undefined)?.route)
    const destination = new URL(route, self.location.origin).href
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    const existing = windows.find(window => new URL(window.url).origin === self.location.origin)
    if (existing) { await existing.navigate(destination); await existing.focus() }
    else await self.clients.openWindow(destination)
  })())
})
