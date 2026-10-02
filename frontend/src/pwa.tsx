import { useEffect, useState } from 'react'
import { Button, Notice } from './components/ui'

interface InstallPrompt extends Event { prompt: () => Promise<void>; userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }> }
let registration: ServiceWorkerRegistration | undefined
export async function registerWorker() {
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return
  try {
    registration = await navigator.serviceWorker.register('/sw.js', { scope: '/' })
    const notify = () => { if (registration?.waiting && navigator.serviceWorker.controller) window.dispatchEvent(new Event('sitrap:update-ready')) }
    notify()
    registration.addEventListener('updatefound', () => registration?.installing?.addEventListener('statechange', notify))
  } catch { window.dispatchEvent(new Event('sitrap:offline-unavailable')) }
}
export function PwaControls() {
  const [install, setInstall] = useState<InstallPrompt | null>(null)
  const [update, setUpdate] = useState(!!registration?.waiting)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    const prompt = (event: Event) => { event.preventDefault(); setInstall(event as InstallPrompt) }
    const ready = () => setUpdate(true)
    const fail = () => setFailed(true)
    window.addEventListener('beforeinstallprompt', prompt)
    window.addEventListener('sitrap:update-ready', ready)
    window.addEventListener('sitrap:offline-unavailable', fail)
    return () => { window.removeEventListener('beforeinstallprompt', prompt); window.removeEventListener('sitrap:update-ready', ready); window.removeEventListener('sitrap:offline-unavailable', fail) }
  }, [])
  return <>
    {install && <Button variant="secondary" onClick={async () => { await install.prompt(); await install.userChoice; setInstall(null) }}>Instalar SITRAP</Button>}
    {update && <Notice>Hay una actualización. Guarda el formulario antes de continuar. <Button variant="secondary" onClick={() => {
      navigator.serviceWorker.addEventListener('controllerchange', () => window.location.reload(), { once: true })
      registration?.waiting?.postMessage({ type: 'SKIP_WAITING' })
    }}>Actualizar aplicación</Button></Notice>}
    {failed && <Notice tone="warning">No se pudo preparar la aplicación para abrir sin conexión. Reintenta con conexión.</Notice>}
  </>
}
