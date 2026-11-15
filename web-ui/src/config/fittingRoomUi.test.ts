import { afterEach, describe, expect, it, vi } from 'vitest'
import { isFittingRoomUiEnabled } from './fittingRoomUi'

describe('isFittingRoomUiEnabled', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('defaults ON when unset (PM-approved)', () => {
    vi.stubEnv('VITE_FITTING_ROOM_UI_ENABLED', undefined)
    expect(isFittingRoomUiEnabled()).toBe(true)
    vi.stubEnv('VITE_FITTING_ROOM_UI_ENABLED', '')
    expect(isFittingRoomUiEnabled()).toBe(true)
  })

  it('enables for explicit truthy values', () => {
    vi.stubEnv('VITE_FITTING_ROOM_UI_ENABLED', 'true')
    expect(isFittingRoomUiEnabled()).toBe(true)
    vi.stubEnv('VITE_FITTING_ROOM_UI_ENABLED', '1')
    expect(isFittingRoomUiEnabled()).toBe(true)
    vi.stubEnv('VITE_FITTING_ROOM_UI_ENABLED', 'yes')
    expect(isFittingRoomUiEnabled()).toBe(true)
  })

  it('disables for explicit falsy values', () => {
    vi.stubEnv('VITE_FITTING_ROOM_UI_ENABLED', 'false')
    expect(isFittingRoomUiEnabled()).toBe(false)
    vi.stubEnv('VITE_FITTING_ROOM_UI_ENABLED', '0')
    expect(isFittingRoomUiEnabled()).toBe(false)
    vi.stubEnv('VITE_FITTING_ROOM_UI_ENABLED', 'off')
    expect(isFittingRoomUiEnabled()).toBe(false)
  })

  it('rejects loose strings', () => {
    vi.stubEnv('VITE_FITTING_ROOM_UI_ENABLED', 'maybe')
    expect(isFittingRoomUiEnabled()).toBe(false)
  })
})
