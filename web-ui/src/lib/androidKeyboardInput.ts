/**
 * Android Capacitor / Chrome soft-keyboard helpers.
 *
 * Fixed overlays that center a tall dialog leave a solid shell-colored void when
 * the WebView scrolls the focused field into view (Look Details rename, Friends
 * add-user, profile edit, etc.). Prefer docking + nearest scroll, not center.
 */

export function isEditableElement(el: EventTarget | null): el is HTMLElement {
  if (!el || !(el instanceof Element)) return false
  const tag = el.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  return Boolean(el instanceof HTMLElement && el.isContentEditable)
}

/** Scroll a field into view without creating a black band above the keyboard. */
export function scrollEditableIntoView(el: HTMLElement | null | undefined): void {
  if (!el) return
  el.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'auto' })
  // Re-assert focus without another scroll jump (Samsung / Chromium quirk).
  if (document.activeElement === el && 'focus' in el) {
    try {
      el.focus({ preventScroll: true })
    } catch {
      /* older WebViews */
    }
  }
}

/**
 * Call from input/textarea onFocus. Defers one frame so adjustResize can settle,
 * then scrolls nearest and re-focuses.
 */
export function onAndroidEditableFocus(el: HTMLElement | null | undefined): void {
  if (!el) return
  window.setTimeout(() => scrollEditableIntoView(el), 50)
}
