import { afterEach, describe, expect, it, vi } from 'vitest'

describe('isRegistrationUiEnabled', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('defaults to disabled when unset', async () => {
    vi.stubEnv('VITE_REGISTRATION_UI_ENABLED', '')
    const { isRegistrationUiEnabled } = await import('./registrationUi')
    expect(isRegistrationUiEnabled()).toBe(false)
  })

  it('enables only for explicit true-like values', async () => {
    vi.stubEnv('VITE_REGISTRATION_UI_ENABLED', 'true')
    const { isRegistrationUiEnabled } = await import('./registrationUi')
    expect(isRegistrationUiEnabled()).toBe(true)
  })

  it('treats false as disabled', async () => {
    vi.stubEnv('VITE_REGISTRATION_UI_ENABLED', 'false')
    const { isRegistrationUiEnabled } = await import('./registrationUi')
    expect(isRegistrationUiEnabled()).toBe(false)
  })
})

describe('canAdvertiseRegistration', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('follows backend availability when known', async () => {
    vi.stubEnv('VITE_REGISTRATION_UI_ENABLED', 'false')
    const { canAdvertiseRegistration } = await import('./registrationUi')
    expect(canAdvertiseRegistration(true)).toBe(true)
    expect(canAdvertiseRegistration(false)).toBe(false)
  })

  it('falls back to Vite flag only when status is unknown', async () => {
    vi.stubEnv('VITE_REGISTRATION_UI_ENABLED', 'true')
    const { canAdvertiseRegistration } = await import('./registrationUi')
    expect(canAdvertiseRegistration(null)).toBe(true)
  })
})
