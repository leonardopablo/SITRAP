/** Push data is untrusted: restrict click targets to authenticated read-only routes. */
export function safePushRoute(value: unknown): string {
  if (value === '/avisos') return '/avisos'
  if (typeof value !== 'string') return '/avisos'
  if (/^\/(entregas|correcciones)\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)) return value
  return '/avisos'
}
export function safeTag(value: unknown) { return typeof value === 'string' && /^[0-9a-f-]{36}$/i.test(value) ? `sitrap:${value}` : 'sitrap:aviso' }
