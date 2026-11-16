import { describe, expect, it } from 'vitest'
import { navigation, roleLabels } from '../auth/workspace'
import { limaToday, purposes } from './types'

describe('Cuyes workspace', () => {
  it('keeps the milk navigation and adds an independent galponero workspace', () => {
    expect(navigation.PRODUCCION.some(n => n.to === '/produccion')).toBe(true)
    expect(navigation.PRODUCCION.some(n => n.to === '/cuyes')).toBe(false)
    expect(navigation.GALPONERO[0].to).toBe('/cuyes')
    expect(navigation.ADMIN.some(n => n.to === '/cuyes')).toBe(true)
    expect(roleLabels.GALPONERO).toContain('Cuyes')
  })
  it('offers the five pen purposes and a Peruvian operational date', () => {
    expect(Object.keys(purposes)).toHaveLength(5)
    expect(limaToday()).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })
})
