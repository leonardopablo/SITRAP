import { safePushRoute, safeTag } from './route'

it('push viejo solo abre ruta interna de lectura; URL externa y acciones nunca se aceptan', () => {
  const id = '11111111-1111-4111-8111-111111111111'
  expect(safePushRoute(`/entregas/${id}`)).toBe(`/entregas/${id}`)
  expect(safePushRoute(`/correcciones/${id}`)).toBe(`/correcciones/${id}`)
  for (const invalid of ['https://evil.test', '//evil.test', `/entregas/${id}/pickup`, '/admin', '/entregas/../cuenta', null]) expect(safePushRoute(invalid)).toBe('/avisos')
  expect(safeTag(id)).toBe(`sitrap:${id}`)
  expect(safeTag('malicious')).toBe('sitrap:aviso')
})
