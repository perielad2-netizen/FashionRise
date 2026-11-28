/**
 * Centralized notification → in-app navigation for all push types.
 *
 * Warm start, cold start, and auth/router races share one pending destination.
 * Do not add per-feature tap handlers.
 */
import { sanitizePushDestination } from './pushDestination'
import { navigateInApp } from './urlPolicy'

const PENDING_KEY = 'fr.push.pendingDestination.v1'

let pendingPath: string | null = null
let lastNavigatedPath: string | null = null
let lastNavigatedAt = 0
let ready = false

/** Deduplicate rapid duplicate taps / retained plugin events (ms). */
const DEDUPE_MS = 2500

function persistPending(path: string | null): void {
  if (typeof window === 'undefined') return
  try {
    if (!path) {
      localStorage.removeItem(PENDING_KEY)
      return
    }
    localStorage.setItem(PENDING_KEY, path)
  } catch {
    /* private mode */
  }
}

function readPersistedPending(): string | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(PENDING_KEY)
    if (!raw) return null
    return sanitizePushDestination(raw)
  } catch {
    return null
  }
}

/** Mark SPA auth + router ready to consume a pending push destination. */
export function setNotificationNavigationReady(isReady: boolean): void {
  ready = isReady
  if (ready) flushPendingNotificationDestination()
}

export function isNotificationNavigationReady(): boolean {
  return ready
}

/**
 * Queue or navigate to a sanitized push destination.
 * Rejects unsafe paths via sanitizePushDestination.
 */
export function handleNotificationDestination(rawUrl: unknown): string {
  const path = sanitizePushDestination(rawUrl)
  const now = Date.now()
  if (
    lastNavigatedPath === path &&
    now - lastNavigatedAt < DEDUPE_MS &&
    ready
  ) {
    return path
  }

  if (!ready) {
    pendingPath = path
    persistPending(path)
    return path
  }

  pendingPath = null
  persistPending(null)
  lastNavigatedPath = path
  lastNavigatedAt = now
  navigateInApp(path)
  return path
}

/** Process a stored pending destination once the shell is ready. */
export function flushPendingNotificationDestination(): string | null {
  if (!ready) return null
  const path = pendingPath || readPersistedPending()
  if (!path) return null
  pendingPath = null
  persistPending(null)
  const now = Date.now()
  if (lastNavigatedPath === path && now - lastNavigatedAt < DEDUPE_MS) {
    return path
  }
  lastNavigatedPath = path
  lastNavigatedAt = now
  navigateInApp(path)
  return path
}

export function peekPendingNotificationDestination(): string | null {
  return pendingPath || readPersistedPending()
}

/**
 * Drop queued destinations on logout / account switch so the next user cannot
 * inherit another account's notification target.
 */
export function clearPendingNotificationDestination(): void {
  pendingPath = null
  persistPending(null)
}

/** Test helper — clear module state between unit tests. */
export function _resetNotificationNavigationForTests(): void {
  pendingPath = null
  lastNavigatedPath = null
  lastNavigatedAt = 0
  ready = false
  persistPending(null)
}
