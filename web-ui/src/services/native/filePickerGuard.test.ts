import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  armNativeFilePickerFocusClear,
  isNativeFilePickerOpen,
  markNativeFilePickerClosed,
  markNativeFilePickerOpen,
} from './filePickerGuard'

describe('filePickerGuard', () => {
  afterEach(() => {
    while (isNativeFilePickerOpen()) markNativeFilePickerClosed()
  })

  it('tracks open/close count for native camera/file pickers', () => {
    expect(isNativeFilePickerOpen()).toBe(false)
    markNativeFilePickerOpen()
    markNativeFilePickerOpen()
    expect(isNativeFilePickerOpen()).toBe(true)
    markNativeFilePickerClosed()
    expect(isNativeFilePickerOpen()).toBe(true)
    markNativeFilePickerClosed()
    expect(isNativeFilePickerOpen()).toBe(false)
  })

  it('clears after focus returns from the system sheet', () => {
    vi.useFakeTimers()
    markNativeFilePickerOpen()
    armNativeFilePickerFocusClear(10)
    window.dispatchEvent(new Event('focus'))
    vi.advanceTimersByTime(20)
    expect(isNativeFilePickerOpen()).toBe(false)
    vi.useRealTimers()
  })
})
