import { afterEach, describe, expect, it, vi } from 'vitest'
import { modalPortalRoot } from '@/lib/modalPortalRoot'

describe('modalPortalRoot', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  it('returns document.body when not fullscreen', () => {
    expect(modalPortalRoot()).toBe(document.body)
  })

  it('returns the fullscreen element when immersive native FS is active', () => {
    const host = document.createElement('section')
    document.body.appendChild(host)
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      get: () => host,
    })
    expect(modalPortalRoot()).toBe(host)
  })

  it('falls back to webkitFullscreenElement when standard FS is empty', () => {
    const host = document.createElement('section')
    document.body.appendChild(host)
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      get: () => null,
    })
    Object.defineProperty(document, 'webkitFullscreenElement', {
      configurable: true,
      get: () => host,
    })
    expect(modalPortalRoot()).toBe(host)
  })
})

