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

test('el contenido se desplaza sin mover la navegación administrativa', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 })
  await page.goto('/acceso')
  await page.getByLabel('Usuario').fill('admin')
  await page.getByLabel('Contraseña').fill('Demostracion123!')
  await page.getByRole('button', { name: 'Ingresar' }).click()
  const menu = page.getByRole('navigation', { name: 'Navegación principal' })
  await menu.getByRole('link', { name: 'Cuentas' }).click()
  await expect(page.getByRole('heading', { name: 'Cuentas y ámbitos' })).toBeVisible()
  const content = page.locator('.workspace-content')
  await content.evaluate(element => { element.scrollTop = 250 })
  await expect.poll(() => content.evaluate(element => element.scrollTop)).toBeGreaterThan(0)
  const before = (await menu.boundingBox())!.y
  await content.evaluate(element => { element.scrollTop += 250 })
  expect((await menu.boundingBox())!.y).toBe(before)
  expect(await page.evaluate(() => window.scrollY)).toBe(0)
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
    expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(1100)
    await expect.poll(() => account.boundingBox().then(box => box!.x)).toBeCloseTo(originalX, 0)
    expect(await page.evaluate(() => document.documentElement.clientWidth)).toBe(availableWidth)
  }
})

test('en móvil, los ajustes de cuenta no desplazan el contenido fuera de la primera pantalla', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 })
  await page.goto('/acceso')
  await page.getByLabel('Usuario').fill('admin')
  await page.getByLabel('Contraseña').fill('Demostracion123!')
  await page.getByRole('button', { name: 'Ingresar' }).click()
  const toggle = page.locator('.workspace-account__toggle')
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  const heading = page.getByRole('heading', { name: 'Resumen administrativo' })
  await expect(heading).toBeVisible()
  const navTop = (await page.getByRole('navigation', { name: 'Navegación principal' }).boundingBox())!.y
  const headingBox = (await heading.boundingBox())!
  expect(headingBox.y + headingBox.height).toBeLessThan(navTop)
  await expect(page.getByRole('link', { name: 'Cambiar contraseña' })).toBeHidden()
  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByRole('link', { name: 'Cambiar contraseña' })).toBeVisible()
  await page.getByRole('button', { name: 'Ocultar opciones de cuenta' }).click()
  await expect(page.getByRole('link', { name: 'Cambiar contraseña' })).toBeHidden()
})

test('ADMIN desplaza solo la barra inferior sin flechas y mantiene visible la opción activa', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 })
  await page.goto('/acceso')
  await page.getByLabel('Usuario').fill('admin')
  await page.getByLabel('Contraseña').fill('Demostracion123!')
  await page.getByRole('button', { name: 'Ingresar' }).click()
  const nav = page.getByRole('navigation', { name: 'Navegación principal' })
  const scroller = nav.locator('.workspace-nav__scroller')
  expect(await scroller.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true)
  expect((await nav.boundingBox())!.height).toBeLessThan(90)
  await expect(nav.getByRole('button')).toHaveCount(0)
  await expect(scroller).toHaveClass(/has-more-right/)
  await scroller.evaluate(element => { element.scrollLeft = element.scrollWidth / 2 })
  await expect(scroller).toHaveClass(/has-more-left/)
  await nav.getByRole('link', { name: 'Catálogos' }).click()
  await expect(nav.getByRole('link', { name: 'Catálogos' })).toHaveAttribute('aria-current', 'page')
  const link = (await nav.getByRole('link', { name: 'Catálogos' }).boundingBox())!
  const visible = (await scroller.boundingBox())!
  expect(link.x).toBeGreaterThanOrEqual(visible.x - 1)
  expect(link.x + link.width).toBeLessThanOrEqual(visible.x + visible.width + 1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)
})

test('la barra móvil de ADMIN conserva su posición al cambiar de vista', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 })
  await page.goto('/acceso')
  await page.getByLabel('Usuario').fill('admin')
  await page.getByLabel('Contraseña').fill('Demostracion123!')
  await page.getByRole('button', { name: 'Ingresar' }).click()
  const nav = page.getByRole('navigation', { name: 'Navegación principal' })
  const scroller = nav.locator('.workspace-nav__scroller')
  await scroller.evaluate(element => { element.scrollLeft = 70 })
  const position = await scroller.evaluate(element => element.scrollLeft)
  await nav.getByRole('link', { name: 'Administrar' }).click()
  await expect(nav.getByRole('link', { name: 'Administrar' })).toHaveAttribute('aria-current', 'page')
  expect(await scroller.evaluate(element => element.scrollLeft)).toBe(position)
})

test('Recepción mantiene una sola fila y desplaza la ayuda lateralmente', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 })
  await page.goto('/acceso')
  await page.getByLabel('Usuario').fill('recepcion')
  await page.getByLabel('Contraseña').fill('Demostracion123!')
  await page.getByRole('button', { name: 'Ingresar' }).click()
  const nav = page.getByRole('navigation', { name: 'Navegación principal' })
  expect(await nav.locator('.workspace-nav__scroller').evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true)
  await expect(nav.getByRole('button')).toHaveCount(0)
  await expect(nav.locator('.workspace-nav__scroller')).toHaveClass(/has-more-right/)
})

for (const [role, expectedGuide] of [
  ['produccion', 'Registrar producción'],
  ['transporte', 'Recoger una entrega'],
  ['recepcion', 'Recibir una entrega'],
  ['admin', 'Trazabilidad'],
] as const) {
  test(`la ayuda explica las operaciones de ${role}`, async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 700 })
    await page.goto('/acceso')
    await page.getByLabel('Usuario').fill(role)
    await page.getByLabel('Contraseña').fill('Demostracion123!')
    await page.getByRole('button', { name: 'Ingresar' }).click()
    const nav = page.getByRole('navigation', { name: 'Navegación principal' })
    const scroller = nav.locator('.workspace-nav__scroller')
    await scroller.evaluate(element => { element.scrollLeft = element.scrollWidth })
    await nav.getByRole('link', { name: 'Ayuda' }).click()
    await expect(page.getByRole('heading', { name: 'Cómo usar SITRAP' })).toBeVisible()
    await expect(page.getByRole('heading', { name: expectedGuide })).toBeVisible()
    await expect(nav.getByRole('link', { name: 'Ayuda' })).toHaveAttribute('aria-current', 'page')
  })
}

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

    test(`el menú de ${role} permite navegar a ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 600 })
      await page.goto('/acceso')
      await page.getByLabel('Usuario').fill(role)
      await page.getByLabel('Contraseña').fill('Demostracion123!')
      await page.getByRole('button', { name: 'Ingresar' }).click()

      const menu = page.getByRole('navigation', { name: 'Navegación principal' })
      await expect(menu).toBeVisible()
      for (const section of sections.slice(1)) {
        const link = menu.getByRole('link', { name: section, exact: true })
        await link.click()
        await expect(link).toHaveAttribute('aria-current', 'page')
      }
    })
  }

  test(`el panel de ${role} desplaza sus opciones independientemente en escritorio`, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 600 })
    await page.goto('/acceso')
    await page.getByLabel('Usuario').fill(role)
    await page.getByLabel('Contraseña').fill('Demostracion123!')
    await page.getByRole('button', { name: 'Ingresar' }).click()
    const sidebar = page.locator('.workspace-sidebar')
    const content = page.locator('.workspace-content')
    const menu = page.getByRole('navigation', { name: 'Navegación principal' })
    const sidebarY = (await sidebar.boundingBox())!.y
    await content.evaluate(element => element.appendChild(Object.assign(document.createElement('div'), { style: 'height: 1800px' })))
    await content.evaluate(element => { element.scrollTop = 300 })
    expect((await sidebar.boundingBox())!.y).toBe(sidebarY)
    expect(await page.evaluate(() => window.scrollY)).toBe(0)
    await sidebar.evaluate(element => element.appendChild(Object.assign(document.createElement('div'), { style: 'height: 1800px' })))
    await sidebar.evaluate(element => { element.scrollTop = 140 })
    await expect.poll(() => sidebar.evaluate(element => element.scrollTop)).toBeGreaterThan(0)
    expect(await content.evaluate(element => element.scrollTop)).toBe(300)
    await sidebar.evaluate(element => { element.scrollTop = 0 })
    await expect(menu.getByRole('link', { name: sections[0], exact: true })).toBeVisible()
  })
}
