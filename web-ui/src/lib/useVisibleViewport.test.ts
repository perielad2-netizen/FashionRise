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
    document.documentElement.style.removeProperty('--fr-visible-height')
    document.documentElement.style.removeProperty('--fr-vv-offset-top')
    document.documentElement.style.removeProperty('--fr-browser-chrome-bottom')
    document.documentElement.classList.remove('fr-native-ios')
    document.documentElement.removeAttribute('data-fr-keyboard')
    vi.restoreAllMocks()
  })

  it('writes visible height and bottom chrome overlap onto :root', () => {
    renderHook(() => useVisibleViewport())
    expect(document.documentElement.style.getPropertyValue('--fr-vv-height')).toBe('740px')
    expect(document.documentElement.style.getPropertyValue('--fr-vv-offset-top')).toBe('0px')
    expect(document.documentElement.style.getPropertyValue('--fr-browser-chrome-bottom')).toBe(
      '60px',
    )
  })

  it('clears vars on unmount', () => {
    const { unmount } = renderHook(() => useVisibleViewport())
    unmount()
    expect(document.documentElement.style.getPropertyValue('--fr-vv-height')).toBe('')
    expect(document.documentElement.style.getPropertyValue('--fr-vv-offset-top')).toBe('')
    expect(document.documentElement.style.getPropertyValue('--fr-browser-chrome-bottom')).toBe('')
  })

  it('resets native scroll jump when visualViewport.offsetTop moves under the keyboard', () => {
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
    document.documentElement.classList.add('fr-native-android')
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()
    Object.defineProperty(window.visualViewport!, 'height', { configurable: true, value: 420 })
    Object.defineProperty(window.visualViewport!, 'offsetTop', { configurable: true, value: 180 })

    renderHook(() => useVisibleViewport())
    expect(document.documentElement.style.getPropertyValue('--fr-vv-offset-top')).toBe('180px')
    expect(scrollTo).toHaveBeenCalledWith(0, 0)
    input.remove()
  })

  it('no-ops when disabled', () => {
    renderHook(() => useVisibleViewport(false))
    expect(document.documentElement.style.getPropertyValue('--fr-vv-height')).toBe('')
  })

  it('does not shrink #root for soft-keyboard occlusion while an input is focused', () => {
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 800 })
    Object.defineProperty(window.visualViewport!, 'height', { configurable: true, value: 420 })

    renderHook(() => useVisibleViewport())
    // Layout height kept — avoids black void above Android keyboard.
    expect(document.documentElement.style.getPropertyValue('--fr-vv-height')).toBe('800px')
    expect(document.documentElement.style.getPropertyValue('--fr-visible-height')).toBe('420px')
    expect(document.documentElement.style.getPropertyValue('--fr-browser-chrome-bottom')).toBe(
      '0px',
    )
    expect(document.documentElement.getAttribute('data-fr-keyboard')).toBe('1')
    input.remove()
  })

  it('always tracks true visual height for fixed dialogs even without keyboard', () => {
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 800 })
    Object.defineProperty(window.visualViewport!, 'height', { configurable: true, value: 740 })
    renderHook(() => useVisibleViewport())
    expect(document.documentElement.style.getPropertyValue('--fr-visible-height')).toBe('740px')
    expect(document.documentElement.getAttribute('data-fr-keyboard')).toBeNull()
  })
})
