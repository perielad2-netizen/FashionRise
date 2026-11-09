import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useVisibleViewport } from '@/lib/useVisibleViewport'

describe('useVisibleViewport', () => {
  const listeners = new Map<string, Set<() => void>>()

  beforeEach(() => {
    listeners.clear()
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 800 })
    const vv = {
      height: 740,
      offsetTop: 0,
      addEventListener: (type: string, cb: () => void) => {
        if (!listeners.has(type)) listeners.set(type, new Set())
        listeners.get(type)!.add(cb)
      },
      removeEventListener: (type: string, cb: () => void) => {
        listeners.get(type)?.delete(cb)
      },
    }
    Object.defineProperty(window, 'visualViewport', {
      configurable: true,
      value: vv,
    })
  })

  afterEach(() => {
    document.documentElement.style.removeProperty('--fr-vv-height')
    document.documentElement.style.removeProperty('--fr-browser-chrome-bottom')
    vi.restoreAllMocks()
  })

  it('writes visible height and bottom chrome overlap onto :root', () => {
    renderHook(() => useVisibleViewport())
    expect(document.documentElement.style.getPropertyValue('--fr-vv-height')).toBe('740px')
    expect(document.documentElement.style.getPropertyValue('--fr-browser-chrome-bottom')).toBe(
      '60px',
    )
  })

  it('clears vars on unmount', () => {
    const { unmount } = renderHook(() => useVisibleViewport())
    unmount()
    expect(document.documentElement.style.getPropertyValue('--fr-vv-height')).toBe('')
    expect(document.documentElement.style.getPropertyValue('--fr-browser-chrome-bottom')).toBe('')
  })

  it('no-ops when disabled', () => {
    renderHook(() => useVisibleViewport(false))
    expect(document.documentElement.style.getPropertyValue('--fr-vv-height')).toBe('')
  })
})
