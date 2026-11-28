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

  it('cold start: queues comment destination then flushes after auth ready', () => {
    const ITEM = '11111111-1111-4111-8111-111111111111'
    const COMMENT = '22222222-2222-4222-8222-222222222222'
    const url = `/studio/fashionrise?item=${ITEM}&comments=1&comment=${COMMENT}`
    handleNotificationDestination(url)
    expect(navigateInApp).not.toHaveBeenCalled()
    expect(peekPendingNotificationDestination()).toBe(url)
    setNotificationNavigationReady(true)
    expect(navigateInApp).toHaveBeenCalledWith(url)
  })

  it('warm start: six event types navigate immediately when ready', () => {
    const ITEM = '11111111-1111-4111-8111-111111111111'
    const COMMENT = '22222222-2222-4222-8222-222222222222'
    const FRIENDSHIP = '33333333-3333-4333-8333-333333333333'
    const urls = [
      `/studio/fashionrise?item=${ITEM}`,
      `/studio/fashionrise?item=${ITEM}`,
      `/studio/fashionrise?item=${ITEM}&comments=1&comment=${COMMENT}`,
      `/studio/fashionrise?item=${ITEM}&comments=1&comment=${COMMENT}`,
      `/studio/fashionrise?friends=1&section=requests&friendship=${FRIENDSHIP}`,
      `/studio/fashionrise?friends=1&section=accepted&friendship=${FRIENDSHIP}`,
    ]
    setNotificationNavigationReady(true)
    for (const url of urls) {
      navigateInApp.mockClear()
      _resetNotificationNavigationForTests()
      setNotificationNavigationReady(true)
      handleNotificationDestination(url)
      expect(navigateInApp).toHaveBeenCalledWith(url)
    }
  })

  it('does not weaken auth routes into push destinations', () => {
    setNotificationNavigationReady(true)
    handleNotificationDestination('/auth/google/complete#access_token=x')
    expect(navigateInApp).toHaveBeenCalledWith('/studio/fashionrise')
  })
})
