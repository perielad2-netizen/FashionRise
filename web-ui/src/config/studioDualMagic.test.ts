import { afterEach, describe, expect, it, vi } from 'vitest'
import { isStudioDualMagicEnabled } from '@/config/studioDualMagic'

describe('isStudioDualMagicEnabled', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('defaults to false when unset or empty', () => {
    vi.stubEnv('VITE_STUDIO_DUAL_MAGIC_ENABLED', '')
    expect(isStudioDualMagicEnabled()).toBe(false)
  })

  it.each(['1', 'true', 'TRUE', 'yes', 'on'] as const)('is true for %s', (value) => {
    vi.stubEnv('VITE_STUDIO_DUAL_MAGIC_ENABLED', value)
    expect(isStudioDualMagicEnabled()).toBe(true)
  })

  it.each(['0', 'false', 'no', 'off', 'maybe'] as const)('is false for %s', (value) => {
    vi.stubEnv('VITE_STUDIO_DUAL_MAGIC_ENABLED', value)
    expect(isStudioDualMagicEnabled()).toBe(false)
  })
})
