import { test, expect } from '@playwright/test'

test('un único worker prepara recursos públicos y permite abrir offline', async ({ page, context }) => {
  await page.goto('/')
  await page.evaluate(async () => { await navigator.serviceWorker.ready })
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Cada producto tiene una historia' })).toBeVisible()
  expect(await page.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length)).toBe(1)
  await context.setOffline(true)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Cada producto tiene una historia' })).toBeVisible()
  expect(await page.locator('img[src="/illustrations/route.svg"]').evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true)
  expect(await page.evaluate(async () => {
    const urls = await Promise.all((await caches.keys()).map(async name => (await (await caches.open(name)).keys()).map(request => request.url)))
    return urls.flat().some(url => new URL(url).pathname.startsWith('/api/'))
  })).toBe(false)
})
