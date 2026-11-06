import { afterEach, describe, expect, it, vi } from 'vitest'
import { isMagicUiEnabled } from '@/config/magicUi'

describe('isMagicUiEnabled', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('defaults off', () => {
    vi.stubEnv('VITE_MAGIC_UI_ENABLED', '')
    expect(isMagicUiEnabled()).toBe(false)
  })

  it('accepts true/1/yes/on', () => {
    for (const value of ['true', '1', 'yes', 'on', 'TRUE']) {
      vi.stubEnv('VITE_MAGIC_UI_ENABLED', value)
      expect(isMagicUiEnabled()).toBe(true)
    }
  })
})
