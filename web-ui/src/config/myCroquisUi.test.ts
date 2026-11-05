import { afterEach, describe, expect, it, vi } from 'vitest'

describe('isMyCroquisUiEnabled', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('defaults OFF when unset', async () => {
    vi.stubEnv('VITE_MY_CROQUIS_UI_ENABLED', undefined)
    const { isMyCroquisUiEnabled } = await import('./myCroquisUi')
    expect(isMyCroquisUiEnabled()).toBe(false)
  })

  it('defaults OFF for empty / falsey strings', async () => {
    for (const raw of ['', '0', 'false', 'no', 'off', 'FALSE']) {
      vi.resetModules()
      vi.stubEnv('VITE_MY_CROQUIS_UI_ENABLED', raw)
      const { isMyCroquisUiEnabled } = await import('./myCroquisUi')
      expect(isMyCroquisUiEnabled()).toBe(false)
    }
  })

  it('enables only for explicit truthy tokens', async () => {
    for (const raw of ['1', 'true', 'yes', 'on', 'TRUE', ' Yes ']) {
      vi.resetModules()
      vi.stubEnv('VITE_MY_CROQUIS_UI_ENABLED', raw)
      const { isMyCroquisUiEnabled } = await import('./myCroquisUi')
      expect(isMyCroquisUiEnabled()).toBe(true)
    }
  })
})
