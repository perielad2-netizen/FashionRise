import { useEffect } from 'react'
import { Keyboard } from '@capacitor/keyboard'

import {
  installGlobalEditableFocusGuards,
  installKeyboardSafeActionGuards,
  isEditableElement,
} from '@/lib/androidKeyboardInput'
import { isNativeShell, nativePlatform } from '@/services/native/platform'

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
 * iOS Capacitor uses `Keyboard.resize: 'none'`, so WKWebView's visualViewport often
 * does **not** shrink when the soft keyboard opens. Fall back to Capacitor's
 * `keyboardWillShow` height on native iOS only — Android/web keep the vv path.
 *
 * Sets on `document.documentElement`:
 * - `--fr-vv-height` — shell / `#root` height in px (layout height while keyboard open)
 * - `--fr-visible-height` — always the true visible height (fixed dialogs/sheets)
 * - `--fr-vv-offset-top` — visualViewport.offsetTop (iOS keyboard scroll jump)
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
    /** Native iOS keyboard height from Capacitor (0 when closed). Web/Android unused. */
    let iosKeyboardHeight = 0

    const sync = () => {
      const layoutH = window.innerHeight || 0
      let visibleH = vv?.height ?? layoutH
      let offsetTop = vv?.offsetTop ?? 0

      // iOS + resize:none — vv often stays at full layout height while the keyboard
      // covers the bottom. Prefer the native keyboard height so chat/comment sheets
      // dock above the keys. Do not apply on Android/web (their vv path works).
      const iosNativeKeyboard =
        isNativeShell() && nativePlatform() === 'ios' && iosKeyboardHeight > 40
      if (iosNativeKeyboard) {
        visibleH = Math.max(1, layoutH - iosKeyboardHeight)
        offsetTop = 0
      }

      const rawChrome = Math.max(0, Math.round(layoutH - visibleH - offsetTop))
      const visiblePx = Math.max(1, Math.round(visibleH || layoutH))
      const offsetTopPx = Math.max(0, Math.round(offsetTop))
      const editing = isEditableFocused() || iosNativeKeyboard

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
      root.style.setProperty('--fr-vv-offset-top', `${offsetTopPx}px`)
      root.style.setProperty('--fr-browser-chrome-bottom', `${chromeBottom}px`)
      if (editing) root.setAttribute('data-fr-keyboard', '1')
      else root.removeAttribute('data-fr-keyboard')

      // Native WKWebView / Chrome scrolls the layout viewport when focusing
      // inputs in fixed overlays, leaving a solid black void under the field.
      if (
        editing &&
        offsetTopPx > 0 &&
        (root.classList.contains('fr-native-ios') ||
          root.classList.contains('fr-native-android'))
      ) {
        window.scrollTo(0, 0)
      }
    }

    sync()
    const disposeFocusGuards = installGlobalEditableFocusGuards()
    const disposeKbdSafeActions = installKeyboardSafeActionGuards()
    vv?.addEventListener('resize', sync)
    vv?.addEventListener('scroll', sync)
    window.addEventListener('resize', sync)
    window.addEventListener('orientationchange', sync)
    // focusin/out: keyboard open/close often does not fire window resize first.
    document.addEventListener('focusin', sync)
    document.addEventListener('focusout', sync)

    const keyboardDisposers: Array<() => void> = []
    if (isNativeShell() && nativePlatform() === 'ios') {
      const onShow = (info: { keyboardHeight: number }) => {
        iosKeyboardHeight = Math.max(0, Math.round(info.keyboardHeight || 0))
        sync()
      }
      const onHide = () => {
        iosKeyboardHeight = 0
        sync()
      }
      void Keyboard.addListener('keyboardWillShow', onShow).then((h) =>
        keyboardDisposers.push(() => h.remove()),
      )
      void Keyboard.addListener('keyboardDidShow', onShow).then((h) =>
        keyboardDisposers.push(() => h.remove()),
      )
      void Keyboard.addListener('keyboardWillHide', onHide).then((h) =>
        keyboardDisposers.push(() => h.remove()),
      )
      void Keyboard.addListener('keyboardDidHide', onHide).then((h) =>
        keyboardDisposers.push(() => h.remove()),
      )
    }

    return () => {
      disposeFocusGuards()
      disposeKbdSafeActions()
      for (const dispose of keyboardDisposers) dispose()
      vv?.removeEventListener('resize', sync)
      vv?.removeEventListener('scroll', sync)
      window.removeEventListener('resize', sync)
      window.removeEventListener('orientationchange', sync)
      document.removeEventListener('focusin', sync)
      document.removeEventListener('focusout', sync)
      root.style.removeProperty('--fr-vv-height')
      root.style.removeProperty('--fr-visible-height')
      root.style.removeProperty('--fr-vv-offset-top')
      root.style.removeProperty('--fr-browser-chrome-bottom')
      root.removeAttribute('data-fr-keyboard')
    }
  }, [enabled])
}
