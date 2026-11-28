import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const remove = vi.fn()
const addListener = vi.fn()

vi.mock('@capacitor/app', () => ({
  App: {
    addListener: (...args: unknown[]) => addListener(...args),
  },
}))

vi.mock('@/services/native/platform', () => ({
  isNativeShell: () => true,
  nativePlatform: () => 'ios',
}))

import { useAppIsActive } from '@/lib/useAppIsActive'

describe('useAppIsActive', () => {
  beforeEach(() => {
    remove.mockReset()
    addListener.mockReset()
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      get: () => 'visible',
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('skips Cap listeners while disabled', () => {
    renderHook(() => useAppIsActive({ enabled: false }))
    expect(addListener).not.toHaveBeenCalled()
  })

  it('registers Cap listener when enabled and removes it on disable', async () => {
    addListener.mockResolvedValue({ remove })
    const { rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) => useAppIsActive({ enabled }),
      { initialProps: { enabled: true } },
    )

    await act(async () => {
      await Promise.resolve()
    })
    expect(addListener).toHaveBeenCalledWith('appStateChange', expect.any(Function))

    rerender({ enabled: false })
    expect(remove).toHaveBeenCalledTimes(1)
  })

  it('removes Cap handle that resolves after unmount', async () => {
    let resolveHandle!: (h: { remove: () => void }) => void
    addListener.mockReturnValue(
      new Promise<{ remove: () => void }>((r) => {
        resolveHandle = r
      }),
    )

    const { unmount } = renderHook(() => useAppIsActive({ enabled: true }))
    unmount()

    await act(async () => {
      resolveHandle({ remove })
      await Promise.resolve()
    })
    expect(remove).toHaveBeenCalledTimes(1)
  })

  it('updates from Cap appStateChange while enabled', async () => {
    let handler: ((state: { isActive: boolean }) => void) | undefined
    addListener.mockImplementation(async (_evt: string, cb: (s: { isActive: boolean }) => void) => {
      handler = cb
      return { remove }
    })

    const { result } = renderHook(() => useAppIsActive({ enabled: true }))
    await act(async () => {
      await Promise.resolve()
    })
    expect(result.current).toBe(true)

    act(() => {
      handler?.({ isActive: false })
    })
    expect(result.current).toBe(false)

    act(() => {
      handler?.({ isActive: true })
    })
    expect(result.current).toBe(true)
  })
})
