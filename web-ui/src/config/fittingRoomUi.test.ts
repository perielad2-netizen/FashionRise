import { afterEach, describe, expect, it, vi } from 'vitest'
import { isFittingRoomUiEnabled } from './fittingRoomUi'

describe('isFittingRoomUiEnabled', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('fails closed by default', () => {
    vi.stubEnv('VITE_FITTING_ROOM_UI_ENABLED', undefined)
    expect(isFittingRoomUiEnabled()).toBe(false)
  })

  it('enables only for explicit truthy values', () => {
    vi.stubEnv('VITE_FITTING_ROOM_UI_ENABLED', 'true')
    expect(isFittingRoomUiEnabled()).toBe(true)
    vi.stubEnv('VITE_FITTING_ROOM_UI_ENABLED', '1')
    expect(isFittingRoomUiEnabled()).toBe(true)
    vi.stubEnv('VITE_FITTING_ROOM_UI_ENABLED', 'yes')
    expect(isFittingRoomUiEnabled()).toBe(true)
  })

  it('rejects loose strings', () => {
    vi.stubEnv('VITE_FITTING_ROOM_UI_ENABLED', 'maybe')
    expect(isFittingRoomUiEnabled()).toBe(false)
  })
})
