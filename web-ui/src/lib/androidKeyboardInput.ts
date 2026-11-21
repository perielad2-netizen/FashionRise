/**
 * Native (Android + iOS Capacitor) / Chrome soft-keyboard helpers.
 *
 * Fixed overlays that center a tall dialog leave a solid shell-colored void when
 * the WebView scrolls the focused field into view (Look Details rename, Friends
 * add-user, profile edit, chat, contact form, etc.). Prefer docking + nearest
 * scroll, not center — and apply it to EVERY text field via a global focusin
 * guard (not only hand-wired inputs).
 */

const NON_TEXT_INPUT_TYPES = new Set([
  'button',
  'checkbox',
  'radio',
  'file',
  'range',
  'color',
  'submit',
  'reset',
  'image',
  'hidden',
])

export function isEditableElement(el: EventTarget | null): el is HTMLElement {
  if (!el || !(el instanceof Element)) return false
  const tag = el.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  return Boolean(el instanceof HTMLElement && el.isContentEditable)
}

/** Text-entry fields only — skip range/file/checkbox (no soft keyboard). */
export function isTextEditableElement(el: EventTarget | null): el is HTMLElement {
  if (!isEditableElement(el)) return false
  if (el.tagName === 'SELECT') return false
  if (el.tagName === 'INPUT') {
    const type = ((el as HTMLInputElement).type || 'text').toLowerCase()
    if (NON_TEXT_INPUT_TYPES.has(type)) return false
  }
  return true
}

/** Scroll a field into view without creating a black band above the keyboard. */
export function scrollEditableIntoView(el: HTMLElement | null | undefined): void {
  if (!el) return
  el.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'auto' })
  // Re-assert focus without another scroll jump (Samsung / Chromium / WKWebView).
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

/** Alias — same helper on iOS and Android native shells. */
export const onNativeEditableFocus = onAndroidEditableFocus

/**
 * Soft-keyboard focus often reflows fixed overlays (data-fr-keyboard CSS).
 * The same tap that focused an input can then land on the scrim as a synthetic
 * click and dismiss the sheet — ignore backdrop dismiss while editing.
 */
export function shouldIgnoreOverlayDismiss(): boolean {
  if (typeof document === 'undefined') return false
  if (document.documentElement.getAttribute('data-fr-keyboard') === '1') return true
  return isEditableElement(document.activeElement)
}

/**
 * Tag the nearest fixed/sticky fullscreen-ish host so global CSS can pin it to
 * the visual viewport while the keyboard is open (chat, profile, contact, etc.).
 */
export function markKeyboardOverlayHost(el: HTMLElement | null | undefined): void {
  if (!el || typeof window === 'undefined') return
  let node: HTMLElement | null = el
  const layoutH = window.innerHeight || 0
  while (node && node !== document.documentElement) {
    if (node.classList.contains('fr-keyboard-overlay')) return
    const style = window.getComputedStyle(node)
    const pos = style.position
    if (pos === 'fixed' || pos === 'sticky') {
      const rect = node.getBoundingClientRect()
      const coversMostHeight = rect.height >= layoutH * 0.35
      const nearTop = rect.top <= 24
      const nearBottom = layoutH - rect.bottom <= 24
      if (coversMostHeight || (nearTop && nearBottom) || rect.height >= layoutH * 0.55) {
        node.classList.add('fr-keyboard-overlay')
        node.dataset.frKeyboardHost = '1'
        return
      }
    }
    node = node.parentElement
  }
}

function handleGlobalFocusIn(event: FocusEvent): void {
  const target = event.target
  if (!isTextEditableElement(target)) return
  try {
    target.focus({ preventScroll: true })
  } catch {
    /* older WebViews */
  }
  markKeyboardOverlayHost(target)
  onNativeEditableFocus(target)
}

/**
 * Install for the whole SPA — every text input gets preventScroll + overlay host
 * marking without per-screen wiring. Pair with the returned disposer (e.g. from
 * useVisibleViewport cleanup).
 */
export function installGlobalEditableFocusGuards(): () => void {
  if (typeof document === 'undefined') return () => undefined
  document.addEventListener('focusin', handleGlobalFocusIn, true)
  return () => {
    document.removeEventListener('focusin', handleGlobalFocusIn, true)
  }
}
