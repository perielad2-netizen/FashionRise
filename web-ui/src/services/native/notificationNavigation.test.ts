import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  _resetNotificationNavigationForTests,
  flushPendingNotificationDestination,
  handleNotificationDestination,
  peekPendingNotificationDestination,
  setNotificationNavigationReady,
} from './notificationNavigation'

const navigateInApp = vi.fn()

vi.mock('./urlPolicy', () => ({
  navigateInApp: (...args: unknown[]) => navigateInApp(...args),
}))

describe('notificationNavigation', () => {
  beforeEach(() => {
    _resetNotificationNavigationForTests()
    navigateInApp.mockReset()
    try {
      localStorage.clear()
    } catch {
      /* ignore */
    }
  })

  it('retains destination until ready, then navigates once', () => {
    expect(handleNotificationDestination('/studio/runway')).toBe('/studio/runway')
    expect(navigateInApp).not.toHaveBeenCalled()
    expect(peekPendingNotificationDestination()).toBe('/studio/runway')

    setNotificationNavigationReady(true)
    expect(navigateInApp).toHaveBeenCalledTimes(1)
    expect(navigateInApp).toHaveBeenCalledWith('/studio/runway')
    expect(peekPendingNotificationDestination()).toBeNull()
  })

  it('navigates immediately when already ready', () => {
    setNotificationNavigationReady(true)
    handleNotificationDestination('https://fashionrise.app/studio/runway')
    expect(navigateInApp).toHaveBeenCalledWith('/studio/runway')
  })

  it('rejects unsafe destinations to the safe fallback', () => {
    setNotificationNavigationReady(true)
    handleNotificationDestination('/reset-password#token=abc')
    expect(navigateInApp).toHaveBeenCalledWith('/studio/fashionrise')
  })

  it('dedupes rapid repeated taps to the same path', () => {
    setNotificationNavigationReady(true)
    handleNotificationDestination('/studio/runway')
    handleNotificationDestination('/studio/runway')
    expect(navigateInApp).toHaveBeenCalledTimes(1)
  })

  it('flush is a no-op without a pending path', () => {
    setNotificationNavigationReady(true)
    expect(flushPendingNotificationDestination()).toBeNull()
    expect(navigateInApp).not.toHaveBeenCalled()
  })
})
