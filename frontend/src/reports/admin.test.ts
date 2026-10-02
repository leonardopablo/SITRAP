import { api } from '../api/client'

it('cuenta admin consulta métricas sin recibir potestad de confirmar por otro', async () => {
  await api.post('/auth/login', { username: 'admin', password: 'Demostracion123!' })
  const me = await api.request<{ capabilities: string[] }>('/auth/me')
  expect(me.capabilities).not.toContain('transporte:operate')
  expect(await api.request('/metrics/milk?from=2026-10-01&to=2026-10-31')).toHaveProperty('total_litres')
  await api.post('/auth/logout')
})
