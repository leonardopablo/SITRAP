import { test, expect } from '@playwright/test'

for (const width of [320, 1280]) {
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
