import { useEffect, useState } from 'react'

/**
 * Portal target for modal dialogs (color picker, confirms, gradients).
 *
 * Native Fullscreen API only paints descendants of `document.fullscreenElement`.
 * Portals into `document.body` disappear / become untappable in immersive
 * full-canvas mode — always prefer the active fullscreen host when present.
 * Includes webkitFullscreenElement for Safari / older Capacitor WebViews.
 */
export function modalPortalRoot(): HTMLElement {
  if (typeof document === 'undefined') {
    throw new Error('modalPortalRoot requires document')
  }
  const doc = document as Document & { webkitFullscreenElement?: Element | null }
  const fs = document.fullscreenElement ?? doc.webkitFullscreenElement ?? null
  if (fs instanceof HTMLElement) return fs
  return document.body
}

/** Live portal host — re-targets when native fullscreen enters/exits. */
export function useModalPortalRoot(): HTMLElement {
  const [root, setRoot] = useState(modalPortalRoot)
  useEffect(() => {
    const sync = () => setRoot(modalPortalRoot())
    sync()
    document.addEventListener('fullscreenchange', sync)
    document.addEventListener('webkitfullscreenchange', sync as EventListener)
    return () => {
      document.removeEventListener('fullscreenchange', sync)
      document.removeEventListener('webkitfullscreenchange', sync as EventListener)
    }
  }, [])
  return root
}
