import { useEffect } from 'react'

/**
 * Sync CSS vars that keep the app shell inside the *visible* viewport.
 *
 * Android Chrome / installed PWA often report `100dvh` taller than what the user
 * can see (system nav / gesture bar / browser chrome). Internal scroll regions
 * then end "early" while Delete / card footers stay clipped under that overlap.
 *
 * Sets on `document.documentElement`:
 * - `--fr-vv-height` — visible viewport height in px
 * - `--fr-browser-chrome-bottom` — layout vs visible bottom overlap in px
 */
export function useVisibleViewport(enabled = true): void {
  useEffect(() => {
    if (!enabled || typeof window === 'undefined') return

    const root = document.documentElement
    const vv = window.visualViewport

    const sync = () => {
      const layoutH = window.innerHeight || 0
      const visibleH = vv?.height ?? layoutH
      const offsetTop = vv?.offsetTop ?? 0
      const chromeBottom = Math.max(0, Math.round(layoutH - visibleH - offsetTop))
      const heightPx = Math.max(1, Math.round(visibleH || layoutH))

      root.style.setProperty('--fr-vv-height', `${heightPx}px`)
      root.style.setProperty('--fr-browser-chrome-bottom', `${chromeBottom}px`)
    }

    sync()
    vv?.addEventListener('resize', sync)
    vv?.addEventListener('scroll', sync)
    window.addEventListener('resize', sync)
    window.addEventListener('orientationchange', sync)

    return () => {
      vv?.removeEventListener('resize', sync)
      vv?.removeEventListener('scroll', sync)
      window.removeEventListener('resize', sync)
      window.removeEventListener('orientationchange', sync)
      root.style.removeProperty('--fr-vv-height')
      root.style.removeProperty('--fr-browser-chrome-bottom')
    }
  }, [enabled])
}
