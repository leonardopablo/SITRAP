import { expect, test } from '@playwright/test'

test('Dirección entra al panel de consulta, filtra centros y no administra', async ({ page }) => {
  await page.goto('/acceso')
  await page.getByLabel('Usuario', { exact: true }).fill('direccion-prueba')
  await page.getByLabel('Contraseña', { exact: true }).fill('Director-test-2026!')
  await page.getByRole('button', { name: 'Ingresar', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Dirección DIPROBSA' })).toBeVisible()
  await expect(page.getByText('10 cuyes al cierre del período')).toBeVisible()
  const center = page.getByLabel('Centro', { exact: true })
  await center.selectOption(process.env.SITRAP_DIRECTION_CENTER!)
  await expect(page.getByRole('heading', { name: 'Actividad del personal' })).toHaveCount(1)
  await expect(page.getByRole('link', { name: 'Cuentas', exact: true })).toHaveCount(0)
  expect((await page.request.get('/api/v1/users')).status()).toBe(403)
})
