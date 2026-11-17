/**
 * Tracks when a native WebView file/camera picker (or OS permission sheet) may be open.
 * Capacitor's global backButton must not call history.back()/exitApp during that window —
 * dismissing the Android CAMERA permission with Back was crashing FashionRise.
 */

let openCount = 0
const listeners = new Set<() => void>()

function notify() {
  for (const fn of listeners) fn()
}

export function markNativeFilePickerOpen(): void {
  openCount += 1
  notify()
}

export function markNativeFilePickerClosed(): void {
  openCount = Math.max(0, openCount - 1)
  notify()
}

export function isNativeFilePickerOpen(): boolean {
  return openCount > 0
}

/** Soft clear after focus returns from the system sheet (cancel or success). */
export function armNativeFilePickerFocusClear(timeoutMs = 800): () => void {
  let cleared = false
  const finish = () => {
    if (cleared) return
    cleared = true
    markNativeFilePickerClosed()
    window.removeEventListener('focus', onFocus)
    document.removeEventListener('visibilitychange', onVis)
  }
  const onFocus = () => {
    window.setTimeout(finish, timeoutMs)
  }
  const onVis = () => {
    if (document.visibilityState === 'visible') window.setTimeout(finish, timeoutMs)
  }
  window.addEventListener('focus', onFocus)
  document.addEventListener('visibilitychange', onVis)
  // Safety: never leave the guard stuck if focus never fires.
  window.setTimeout(finish, 60_000)
  return finish
}

export function subscribeNativeFilePicker(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}
