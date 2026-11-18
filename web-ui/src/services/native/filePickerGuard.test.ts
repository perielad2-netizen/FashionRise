import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@capacitor/app', () => ({
  App: {
    toggleBackButtonHandler: vi.fn(async () => undefined),
  },
}))

vi.mock('./platform', () => ({
  isNativeShell: () => true,
  nativePlatform: () => 'android',
}))

import { App } from '@capacitor/app'
import {
  __resetNativeFilePickerGuardForTests,
  armNativeFilePickerForInput,
  isNativeFilePickerOpen,
  markNativeFilePickerClosed,
  markNativeFilePickerOpen,
  wasNativeFilePickerRecentlyOpen,
} from './filePickerGuard'

describe('filePickerGuard', () => {
  beforeEach(() => {
    __resetNativeFilePickerGuardForTests()
    vi.mocked(App.toggleBackButtonHandler).mockClear()
  })

  afterEach(() => {
    __resetNativeFilePickerGuardForTests()
    vi.useRealTimers()
  })

  it('tracks open/close count for native camera/file pickers', () => {
    expect(isNativeFilePickerOpen()).toBe(false)
    markNativeFilePickerOpen()
    markNativeFilePickerOpen()
    expect(isNativeFilePickerOpen()).toBe(true)
    markNativeFilePickerClosed()
    expect(isNativeFilePickerOpen()).toBe(true)
    markNativeFilePickerClosed()
    // sticky window keeps open briefly
    expect(isNativeFilePickerOpen()).toBe(true)
  })

  it('disables Capacitor back handler while camera input is armed', async () => {
    vi.useFakeTimers()
    const input = document.createElement('input')
    input.type = 'file'
    armNativeFilePickerForInput(input, { camera: true })
    expect(App.toggleBackButtonHandler).toHaveBeenCalledWith({ enabled: false })
    expect(isNativeFilePickerOpen()).toBe(true)

    input.dispatchEvent(new Event('cancel'))
    await vi.advanceTimersByTimeAsync(400)
    expect(App.toggleBackButtonHandler).toHaveBeenCalledWith({ enabled: true })
  })

  it('keeps a recent grace after close so Back does not exitApp', () => {
    vi.useFakeTimers()
    vi.setSystemTime(1_000_000)
    markNativeFilePickerOpen()
    markNativeFilePickerClosed()
    expect(wasNativeFilePickerRecentlyOpen()).toBe(true)
    vi.setSystemTime(1_000_000 + 10_000)
    expect(wasNativeFilePickerRecentlyOpen()).toBe(false)
  })

  it('allows a second Camera arm after cancel clears the first guard', async () => {
    vi.useFakeTimers()
    const first = document.createElement('input')
    first.type = 'file'
    const finishFirst = armNativeFilePickerForInput(first, { camera: true })
    first.dispatchEvent(new Event('cancel'))
    await vi.advanceTimersByTimeAsync(400)
    finishFirst()
    __resetNativeFilePickerGuardForTests()

    const second = document.createElement('input')
    second.type = 'file'
    armNativeFilePickerForInput(second, { camera: true })
    expect(App.toggleBackButtonHandler).toHaveBeenCalledWith({ enabled: false })
    expect(isNativeFilePickerOpen()).toBe(true)
    second.dispatchEvent(new Event('cancel'))
    await vi.advanceTimersByTimeAsync(400)
    expect(App.toggleBackButtonHandler).toHaveBeenLastCalledWith({ enabled: true })
  })
})
