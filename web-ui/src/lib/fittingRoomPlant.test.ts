import { beforeEach, describe, expect, it } from 'vitest'
import {
  consumeFittingRoomPlantedNotice,
  FITTING_ROOM_PLANTED_NOTICE_KEY,
} from './fittingRoomStore'

describe('fitting room planted notice', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('stores a one-shot planted notice and consumes it once', () => {
    sessionStorage.setItem(
      FITTING_ROOM_PLANTED_NOTICE_KEY,
      JSON.stringify({
        title: 'Silk dress',
        galleryItemId: 'g1',
        at: '2026-11-18T00:00:00Z',
      }),
    )
    const first = consumeFittingRoomPlantedNotice()
    expect(first).toEqual({
      title: 'Silk dress',
      galleryItemId: 'g1',
      at: '2026-11-18T00:00:00Z',
    })
    expect(consumeFittingRoomPlantedNotice()).toBeNull()
  })

  it('returns null for corrupt payloads', () => {
    sessionStorage.setItem(FITTING_ROOM_PLANTED_NOTICE_KEY, '{not-json')
    expect(consumeFittingRoomPlantedNotice()).toBeNull()
  })
})
