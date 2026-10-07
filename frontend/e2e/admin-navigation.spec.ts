import { test, expect } from '@playwright/test'

test('solo se resalta la sección administrativa abierta', async ({ page }) => {
  await page.goto('/acceso')
  await page.getByLabel('Usuario').fill('admin')
  await page.getByLabel('Contraseña').fill('Demostracion123!')
  await page.getByRole('button', { name: 'Ingresar' }).click()

  const menu = page.getByRole('navigation', { name: 'Navegación principal' })
  for (const section of ['Resumen', 'Administrar', 'Cuentas', 'Catálogos', 'Resumen']) {
    const link = menu.getByRole('link', { name: section, exact: true })
    await link.click()
    await expect(link).toHaveAttribute('aria-current', 'page')
    await expect(menu.locator('[aria-current="page"]')).toHaveCount(1)
  }
})

test('cambiar entre páginas largas no devuelve el scroll al inicio', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 })
  await page.goto('/acceso')
  await page.getByLabel('Usuario').fill('admin')
  await page.getByLabel('Contraseña').fill('Demostracion123!')
  await page.getByRole('button', { name: 'Ingresar' }).click()
  const menu = page.getByRole('navigation', { name: 'Navegación principal' })
  await menu.getByRole('link', { name: 'Cuentas' }).click()
  await expect(page.getByRole('heading', { name: 'Cuentas y ámbitos' })).toBeVisible()
  await page.evaluate(() => window.scrollTo(0, 250))
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(250)
  for (const section of ['Catálogos', 'Cuentas']) {
    const link = menu.getByRole('link', { name: section, exact: true })
    await link.click()
    await expect(link).toHaveAttribute('aria-current', 'page')
    expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0)
  }
})

test('la cuenta no salta lateralmente entre Administrar y Cuentas', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 })
  await page.goto('/acceso')
  await page.getByLabel('Usuario').fill('admin')
  await page.getByLabel('Contraseña').fill('Demostracion123!')
  await page.getByRole('button', { name: 'Ingresar' }).click()
  const menu = page.getByRole('navigation', { name: 'Navegación principal' })
  const account = page.getByRole('region', { name: 'Cuenta y ámbito activos' })
  await menu.getByRole('link', { name: 'Administrar' }).click()
  await expect(page.getByRole('heading', { name: 'Resumen administrativo' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(1100)
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).scrollbarGutter)).toBe('stable')
  const originalX = (await account.boundingBox())!.x
  const availableWidth = await page.evaluate(() => document.documentElement.clientWidth)
  for (const section of ['Cuentas', 'Administrar', 'Cuentas', 'Administrar']) {
    const link = menu.getByRole('link', { name: section })
    await link.click()
    await expect(link).toHaveAttribute('aria-current', 'page')
    if (section === 'Cuentas') expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeGreaterThan(1100)
    await expect.poll(() => account.boundingBox().then(box => box!.x)).toBeCloseTo(originalX, 0)
    expect(await page.evaluate(() => document.documentElement.clientWidth)).toBe(availableWidth)
  }
})

for (const [role, sections] of [
  ['produccion', ['Hoy', 'Producción', 'Vacas', 'Historial']],
  ['transporte', ['Hoy', 'Diario', 'Pendientes']],
  ['recepcion', ['Hoy', 'Recepciones', 'Pendientes']],
] as const) {
  for (const width of [320, 1280]) {
    test(`el menú de ${role} marca una sola opción a ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 760 })
      await page.goto('/acceso')
      await page.getByLabel('Usuario').fill(role)
      await page.getByLabel('Contraseña').fill('Demostracion123!')
      await page.getByRole('button', { name: 'Ingresar' }).click()

      const menu = page.getByRole('navigation', { name: 'Navegación principal' })
      for (const section of sections) {
        const link = menu.getByRole('link', { name: section, exact: true })
        await link.click()
        await expect(link).toHaveAttribute('aria-current', 'page')
        await expect(menu.locator('[aria-current="page"]')).toHaveCount(1)
      }
    })

    test(`el menú de ${role} no fuerza volver arriba a ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 600 })
      await page.goto('/acceso')
      await page.getByLabel('Usuario').fill(role)
      await page.getByLabel('Contraseña').fill('Demostracion123!')
      await page.getByRole('button', { name: 'Ingresar' }).click()

      const menu = page.getByRole('navigation', { name: 'Navegación principal' })
      await expect(menu).toBeVisible()
      await page.evaluate(() => window.scrollTo(0, 90))
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(90)
      for (const section of sections.slice(1)) {
        const link = menu.getByRole('link', { name: section, exact: true })
        await link.click()
        await expect(link).toHaveAttribute('aria-current', 'page')
        expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0)
      }
    })
  }
}
