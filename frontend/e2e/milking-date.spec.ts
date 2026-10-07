import { test, expect } from '@playwright/test'

test('producción solo muestra la fecha actual de Perú y no permite editarla', async ({ page }) => {
  await page.goto('/acceso')
  await page.getByLabel('Usuario').fill('produccion')
  await page.getByLabel('Contraseña').fill('Demostracion123!')
  await page.getByRole('button', { name: 'Ingresar' }).click()
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('link', { name: 'Producción' }).click()
  const date = page.getByLabel('Fecha de ordeño')
  await expect(date).toHaveAttribute('readonly', '')
  const today = await page.evaluate(() => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()))
  await expect(date).toHaveValue(today)
})
