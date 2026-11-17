/**
 * Tracks when a native WebView file/camera picker (or OS CAMERA permission sheet)
 * may be open.
 *
 * Android crash loop (Fitting Room Take photo):
 * 1) Capacitor OnBackPressedCallback consumes Back while the permission dialog is up
 * 2) Our listener called App.exitApp() → Activity.finish() mid permission/file callback
 * 3) WebView filePathCallback never cleared → next Camera tap crashes → "keeps stopping"
 *
 * Fix: keep a sticky open window, disable Capacitor's back handler for that window,
 * never exitApp from backButton (minimize instead), and only clear after input
 * change/cancel or a real resume from background.
 */

import { App } from '@capacitor/app'
import { isNativeShell, nativePlatform } from './platform'

let openCount = 0
let stickyUntilMs = 0
let recentUntilMs = 0
const listeners = new Set<() => void>()

const STICKY_MS = 2_500
const RECENT_MS = 2_000
const RESUME_CLEAR_MS = 1_200

function notify() {
  for (const fn of listeners) fn()
}

function now() {
  return Date.now()
}

async function setCapacitorBackHandlerEnabled(enabled: boolean): Promise<void> {
  if (!isNativeShell() || nativePlatform() !== 'android') return
  try {
    await App.toggleBackButtonHandler({ enabled })
  } catch {
    /* older shell / web */
  }
}

export function markNativeFilePickerOpen(): void {
  openCount += 1
  stickyUntilMs = Math.max(stickyUntilMs, now() + STICKY_MS)
  recentUntilMs = Math.max(recentUntilMs, stickyUntilMs + RECENT_MS)
  notify()
  if (openCount === 1) {
    void setCapacitorBackHandlerEnabled(false)
  }
}

export function markNativeFilePickerClosed(): void {
  openCount = Math.max(0, openCount - 1)
  recentUntilMs = Math.max(recentUntilMs, now() + RECENT_MS)
  notify()
  if (openCount === 0) {
    void setCapacitorBackHandlerEnabled(true)
  }
}

export function isNativeFilePickerOpen(): boolean {
  return openCount > 0 || now() < stickyUntilMs
}

/** True for a short grace after the sheet closes — still ignore Back / avoid exitApp. */
export function wasNativeFilePickerRecentlyOpen(): boolean {
  return isNativeFilePickerOpen() || now() < recentUntilMs
}

/**
 * Arm open + clear when the HTML file input finishes (change/cancel) or the app
 * resumes after the system sheet. Prefer this over focus-only clearing.
 */
export function armNativeFilePickerForInput(
  input: HTMLInputElement | null,
  opts: { camera?: boolean } = {},
): () => void {
  markNativeFilePickerOpen()
  let cleared = false
  let sawHidden = false

  const finish = () => {
    if (cleared) return
    cleared = true
    markNativeFilePickerClosed()
    input?.removeEventListener('change', onDone)
    input?.removeEventListener('cancel', onDone)
    window.removeEventListener('focus', onFocus)
    document.removeEventListener('visibilitychange', onVis)
  }

  const onDone = () => {
    // Let Capacitor finish filePathCallback before we re-enable Back.
    window.setTimeout(finish, 300)
  }

  const onFocus = () => {
    // Only clear on focus if we already left the page (permission / camera Activity).
    if (!sawHidden && !opts.camera) return
    window.setTimeout(() => {
      if (document.visibilityState === 'visible') finish()
    }, RESUME_CLEAR_MS)
  }

  const onVis = () => {
    if (document.visibilityState === 'hidden') {
      sawHidden = true
      return
    }
    if (sawHidden && document.visibilityState === 'visible') {
      window.setTimeout(finish, RESUME_CLEAR_MS)
    }
  }

  input?.addEventListener('change', onDone)
  input?.addEventListener('cancel', onDone)
  window.addEventListener('focus', onFocus)
  document.addEventListener('visibilitychange', onVis)
  // Safety: never leave Back disabled forever.
  window.setTimeout(finish, 90_000)

  return finish
}

/** @deprecated Prefer armNativeFilePickerForInput — kept for tests/callers. */
export function armNativeFilePickerFocusClear(timeoutMs = RESUME_CLEAR_MS): () => void {
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
  window.setTimeout(finish, 60_000)
  return finish
}

export function subscribeNativeFilePicker(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** Test helper — reset module state between cases. */
export function __resetNativeFilePickerGuardForTests(): void {
  openCount = 0
  stickyUntilMs = 0
  recentUntilMs = 0
}
