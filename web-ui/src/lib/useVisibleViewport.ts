import { useEffect } from 'react'

import { isEditableElement } from '@/lib/androidKeyboardInput'

/**
 * Sync CSS vars that keep the app shell inside the *visible* viewport.
 *
 * Android Chrome / installed PWA often report `100dvh` taller than what the user
 * can see (system nav / gesture bar / browser chrome). Internal scroll regions
 * then end "early" while Delete / card footers stay clipped under that overlap.
 *
 * Soft keyboard is different: shrinking `#root` to `visualViewport.height` while
 * the layout viewport is still tall (or while screens also pad by the occlusion)
 * leaves a solid shell-colored void above the keyboard and can drop input focus
 * (Runway Friends / Look Details rename “black square” on Android).
 *
 * Sets on `document.documentElement`:
 * - `--fr-vv-height` — shell / `#root` height in px (layout height while keyboard open)
 * - `--fr-visible-height` — always the true visualViewport height (fixed dialogs/sheets)
 * - `--fr-browser-chrome-bottom` — layout vs visible bottom overlap in px
 * - `data-fr-keyboard` — `"1"` while an editable field is focused
 */

function isEditableFocused(): boolean {
  return isEditableElement(document.activeElement)
}

export function useVisibleViewport(enabled = true): void {
  useEffect(() => {
    if (!enabled || typeof window === 'undefined') return

    const root = document.documentElement
    const vv = window.visualViewport

    const sync = () => {
      const layoutH = window.innerHeight || 0
      const visibleH = vv?.height ?? layoutH
      const offsetTop = vv?.offsetTop ?? 0
      const rawChrome = Math.max(0, Math.round(layoutH - visibleH - offsetTop))
      const visiblePx = Math.max(1, Math.round(visibleH || layoutH))
      const editing = isEditableFocused()

      // Soft keyboard: keep layout height so `#root` does not collapse into a
      // black band above the keyboard. Browser chrome still uses vv height.
      const keyboardOcclusion = editing && rawChrome > 40
      const chromeBottom = keyboardOcclusion ? 0 : rawChrome
      const heightPx = Math.max(
        1,
        Math.round(keyboardOcclusion ? layoutH || visibleH : visibleH || layoutH),
      )

      root.style.setProperty('--fr-vv-height', `${heightPx}px`)
      root.style.setProperty('--fr-visible-height', `${visiblePx}px`)
      root.style.setProperty('--fr-browser-chrome-bottom', `${chromeBottom}px`)
      if (editing) root.setAttribute('data-fr-keyboard', '1')
      else root.removeAttribute('data-fr-keyboard')
    }

    sync()
    vv?.addEventListener('resize', sync)
    vv?.addEventListener('scroll', sync)
    window.addEventListener('resize', sync)
    window.addEventListener('orientationchange', sync)
    // focusin/out: keyboard open/close often does not fire window resize first.
    document.addEventListener('focusin', sync)
    document.addEventListener('focusout', sync)

    return () => {
      vv?.removeEventListener('resize', sync)
      vv?.removeEventListener('scroll', sync)
      window.removeEventListener('resize', sync)
      window.removeEventListener('orientationchange', sync)
      document.removeEventListener('focusin', sync)
      document.removeEventListener('focusout', sync)
      root.style.removeProperty('--fr-vv-height')
      root.style.removeProperty('--fr-visible-height')
      root.style.removeProperty('--fr-browser-chrome-bottom')
      root.removeAttribute('data-fr-keyboard')
    }
  }, [enabled])
}
