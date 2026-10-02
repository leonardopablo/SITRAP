/// <reference lib="webworker" />
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'

declare const self: ServiceWorkerGlobalScope & { __WB_MANIFEST: Array<{ url: string; revision: string | null }> }
precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()
// Only public application assets: authenticated API responses are never cached by SW.
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html'), { denylist: [/^\/api\//] }))
// Updates wait for explicit acceptance. Outbox persists independently in IndexedDB.
self.addEventListener('message', event => { if (event.data?.type === 'SKIP_WAITING') void self.skipWaiting() })
// F25 adds push + notificationclick to THIS worker; never register a second worker.
