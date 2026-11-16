import { expect, test, type Locator } from '@playwright/test'

async function selectCohort(select: Locator, text: string) {
  const value = await select.locator('option').filter({ hasText: text }).first().getAttribute('value')
  await select.selectOption(value!)
}

test('recorrido móvil Cuyes contra Django/PostgreSQL real, sin mock', async ({ page, browser }) => {
  await page.goto('/acceso')
  await page.getByLabel('Usuario', { exact: true }).fill('galponero')
  await page.getByLabel('Contraseña', { exact: true }).fill('Cuyes-local-test-123!')
  await page.getByRole('button', { name: 'Ingresar', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Cuyes · Inventario por poza' })).toBeVisible()
  await page.getByLabel('Galpón', { exact: true }).first().selectOption(process.env.SITRAP_TEST_SHED!)
  await page.getByLabel('Poza', { exact: true }).selectOption(process.env.SITRAP_TEST_PEN!)
  const form = page.getByRole('heading', { name: 'Registrar novedad', exact: true }).locator('..')
  await form.getByLabel('Operación', { exact: true }).selectOption('CUY_OPEN')
  await form.getByLabel('Procedencia del grupo').fill('Conteo físico de prueba aislada')
  await form.getByLabel('Categoría', { exact: true }).selectOption('HEMBRA')
  await form.getByLabel('Cantidad observada').fill('5')
  await form.getByRole('button', { name: 'Añadir línea' }).click()
  await form.getByLabel('Cantidad observada').nth(1).fill('2')
  await form.getByRole('button', { name: 'Añadir línea' }).click()
  await form.getByLabel('Categoría', { exact: true }).nth(2).selectOption('LACTANTE')
  await form.getByLabel('Cantidad observada').nth(2).fill('10')
  await form.getByLabel('Motivo / causa probable').fill('Apertura física verificada')
  await form.getByRole('button', { name: 'Guardar novedad', exact: true }).click()
  await expect(form.getByText('Aceptada por el servidor.', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: /CAN-G1-P01.*17 \/ 100/ })).toBeVisible()

  await page.goto('/sincronizacion')
  await page.getByRole('button', { name: 'Preparar dispositivo' }).click()
  await expect(page.getByText('Datos preparados en este teléfono. No son confirmaciones de negocio.')).toBeVisible()
  await page.getByRole('link', { name: 'Cuyes', exact: true }).click()
  await page.getByLabel('Poza', { exact: true }).selectOption(process.env.SITRAP_TEST_PEN!)
  await form.getByLabel('Operación', { exact: true }).selectOption('CUY_BIRTH')
  await form.getByLabel('Lote de maternidad').selectOption({ index: 1 })
  await form.getByLabel('Nacidos vivos', { exact: true }).fill('3')
  await form.getByLabel('Natimortos (no suman inventario)').fill('1')
  await form.getByLabel('Motivo / causa probable').fill('Nacimiento verificado')
  await form.getByRole('button', { name: 'Guardar novedad', exact: true }).click()
  await expect(page.getByRole('button', { name: /CAN-G1-P01.*20 \/ 100/ })).toBeVisible()

  await form.getByLabel('Operación', { exact: true }).selectOption('CUY_DEATH')
  await selectCohort(form.getByLabel('Lote / ocupación'), 'Conteo físico de prueba aislada')
  await form.getByLabel('Cantidad', { exact: true }).fill('1')
  await form.getByLabel('Motivo / causa probable').fill('desconocida')
  await form.getByRole('button', { name: 'Guardar novedad', exact: true }).click()
  await expect(page.getByRole('button', { name: /CAN-G1-P01.*19 \/ 100/ })).toBeVisible()

  await form.getByLabel('Operación', { exact: true }).selectOption('CUY_WEAN')
  await selectCohort(form.getByLabel('Lote de maternidad'), 'Conteo físico de prueba aislada')
  await form.getByLabel('Poza de destino').selectOption(process.env.SITRAP_TEST_MALES!)
  await form.getByLabel('Cantidad', { exact: true }).fill('3')
  await form.getByRole('button', { name: 'Añadir línea' }).click()
  await form.getByLabel('Categoría', { exact: true }).nth(1).selectOption('HEMBRA')
  await form.getByLabel('Poza de destino').nth(1).selectOption(process.env.SITRAP_TEST_FEMALES!)
  await form.getByLabel('Cantidad', { exact: true }).nth(1).fill('4')
  await form.getByLabel('Motivo / causa probable').fill('Destete repartido verificado')
  await form.getByRole('button', { name: 'Guardar novedad', exact: true }).click()
  await expect(page.getByRole('button', { name: /CAN-G1-P01.*12 \/ 100/ })).toBeVisible()

  // Count each cohort separately, including the newborn cohort.
  await form.getByLabel('Operación', { exact: true }).selectOption('CUY_COUNT')
  const countRows = [
    { cohort: 1, category: 'MACHO', n: '0' },
    { cohort: 1, category: 'HEMBRA', n: '5' },
    { cohort: 1, category: 'LACTANTE', n: '3' },
    { cohort: 2, category: 'LACTANTE', n: '3' },
  ]
  for (const [i, row] of countRows.entries()) {
    if (i) await form.getByRole('button', { name: 'Añadir línea' }).click()
    await selectCohort(form.getByLabel('Lote / ocupación').nth(i), row.cohort === 1 ? 'Conteo físico de prueba aislada' : 'Nacimiento en')
    await form.getByLabel('Categoría', { exact: true }).nth(i).selectOption(row.category)
    await form.getByLabel('Cantidad observada').nth(i).fill(row.n)
  }
  await form.getByLabel('Motivo / causa probable').fill('Conteo mensual con diferencia de un macho')
  await form.getByRole('button', { name: 'Guardar novedad', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Conteo .* PENDIENTE/ })).toBeVisible()
  await form.getByLabel('Operación', { exact: true }).selectOption('CUY_CLOSE')
  await form.getByLabel('Motivo / causa probable').fill('Novedades del día completas')
  await form.getByRole('button', { name: 'Guardar cierre definitivo' }).click()
  await expect(page.getByText(/Parte .*: CERRADO/)).toBeVisible()

  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const admin = await context.newPage()
  await admin.goto('/acceso')
  await admin.getByLabel('Usuario', { exact: true }).fill('vilma')
  await admin.getByLabel('Contraseña', { exact: true }).fill('Cuyes-local-test-123!')
  await admin.getByRole('button', { name: 'Ingresar', exact: true }).click()
  await admin.getByRole('link', { name: 'Cuyes', exact: true }).click()
  await admin.getByLabel('Galpón', { exact: true }).first().selectOption(process.env.SITRAP_TEST_SHED!)
  await admin.getByLabel('Poza', { exact: true }).selectOption(process.env.SITRAP_TEST_PEN!)
  await admin.getByLabel('Motivo para la acción').fill('Reapertura y conciliación física comprobadas')
  await admin.getByRole('button', { name: 'Reabrir con motivo' }).click()
  await expect(admin.getByText(/Parte .*: ABIERTO/)).toBeVisible()
  await admin.getByRole('button', { name: 'Aprobar ajuste' }).click()
  await expect(admin.getByRole('button', { name: /CAN-G1-P01.*11 \/ 100/ })).toBeVisible()
  await expect(admin.getByRole('heading', { name: /Conteo .* APLICADO/ })).toBeVisible()
  await context.close()
})
