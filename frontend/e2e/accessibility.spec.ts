import { test, expect } from '@playwright/test'

for (const width of [320, 1280]) {
  test(`el acceso queda centrado y utilizable a ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 760 })
    await page.goto('/acceso')
    const card = page.locator('.auth-card')
    await expect(card).toBeVisible()
    const bounds = await card.boundingBox()
    const header = await page.locator('header.auth-header').boundingBox()
    const main = await page.locator('main').boundingBox()
    const logo = await page.locator('header.auth-header img').boundingBox()
    expect(bounds).not.toBeNull()
    expect(header).not.toBeNull()
    expect(main).not.toBeNull()
    expect(logo).not.toBeNull()
    expect(Math.abs(bounds!.x - (width - bounds!.x - bounds!.width))).toBeLessThanOrEqual(2)
    expect(Math.abs(logo!.x - (width - logo!.x - logo!.width))).toBeLessThanOrEqual(2)
    expect(logo!.width).toBeGreaterThanOrEqual(200)
    if (header!.height + main!.height <= 760) {
      expect(Math.abs((header!.y + main!.y + main!.height) / 2 - 380)).toBeLessThanOrEqual(2)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    expect(await page.getByRole('heading', { name: 'Acceso a SITRAP' }).evaluate(element => getComputedStyle(element).textAlign)).toBe('center')
    await expect(page.getByLabel('Usuario')).toBeVisible()
    await expect(page.getByLabel('Contraseña')).toBeVisible()
  })

  test(`acceso y navegación por teclado sin desborde horizontal a ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 760 })
    await page.goto('/')
    await page.keyboard.press('Tab')
    await expect(page.getByRole('link', { name: 'Saltar al contenido' })).toBeFocused()
    await page.getByRole('link', { name: 'Ingresar' }).click()
    await page.getByLabel('Usuario').fill('transporte')
    await page.getByLabel('Contraseña').fill('Demostracion123!')
    await page.getByRole('button', { name: 'Ingresar' }).click()
    await expect(page.getByRole('heading', { name: 'Hoy' })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await page.getByRole('link', { name: 'Diario', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Diario de transporte' })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  })
}

test('reducir movimiento desactiva el gesto de acuse y conserva texto', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  await expect(page.locator('html')).toBeVisible()
  const disabled = await page.evaluate(() => {
    const symbol = document.createElement('span')
    symbol.className = 'accepted-mark__symbol'
    document.body.append(symbol)
    const duration = getComputedStyle(symbol).animationDuration
    symbol.remove()
    return duration
  })
  expect(disabled).toBe('0s')
})
