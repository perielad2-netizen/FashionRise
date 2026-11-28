/**
 * Centralized notification → in-app navigation for all push types.
 *
 * Warm start, cold start, and auth/router races share one pending destination.
 * Do not add per-feature tap handlers.
 */
import { sanitizePushDestination } from './pushDestination'
import { navigateInApp } from './urlPolicy'

const PENDING_KEY = 'fr.push.pendingDestination.v1'
/** Pending destinations expire so logout/session gaps cannot revive stale taps. */
const PENDING_TTL_MS = 30 * 60 * 1000

let pendingPath: string | null = null
let pendingExpiresAt = 0
let lastNavigatedPath: string | null = null
let lastNavigatedAt = 0
let ready = false

/** Deduplicate rapid duplicate taps / retained plugin events (ms). */
const DEDUPE_MS = 2500

type PersistedPending = { path: string; exp: number }

function persistPending(path: string | null, exp = 0): void {
  if (typeof window === 'undefined') return
  try {
    if (!path) {
      localStorage.removeItem(PENDING_KEY)
      return
    }
    const payload: PersistedPending = { path, exp: exp || Date.now() + PENDING_TTL_MS }
    localStorage.setItem(PENDING_KEY, JSON.stringify(payload))
  } catch {
    /* private mode */
  }
}

function readPersistedPending(): string | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(PENDING_KEY)
    if (!raw) return null
    // Legacy: bare path string
    if (raw.startsWith('/')) {
      const safe = sanitizePushDestination(raw)
      persistPending(null)
      return safe
    }
    const parsed = JSON.parse(raw) as PersistedPending
    if (!parsed?.path || typeof parsed.exp !== 'number') {
      persistPending(null)
      return null
    }
    if (Date.now() > parsed.exp) {
      persistPending(null)
      return null
    }
    return sanitizePushDestination(parsed.path)
  } catch {
    persistPending(null)
    return null
  }
}

function clearMemoryPending(): void {
  pendingPath = null
  pendingExpiresAt = 0
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
 * Rapid taps: latest destination wins (overwrites pending / navigates anew).
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
    pendingExpiresAt = now + PENDING_TTL_MS
    persistPending(path, pendingExpiresAt)
    return path
  }

  clearMemoryPending()
  persistPending(null)
  lastNavigatedPath = path
  lastNavigatedAt = now
  navigateInApp(path)
  return path
}

/** Process a stored pending destination once the shell is ready. */
export function flushPendingNotificationDestination(): string | null {
  if (!ready) return null
  const now = Date.now()
  if (pendingPath && pendingExpiresAt && now > pendingExpiresAt) {
    clearMemoryPending()
    persistPending(null)
  }
  const path = pendingPath || readPersistedPending()
  if (!path) return null
  clearMemoryPending()
  persistPending(null)
  if (lastNavigatedPath === path && now - lastNavigatedAt < DEDUPE_MS) {
    return path
  }
  lastNavigatedPath = path
  lastNavigatedAt = now
  navigateInApp(path)
  return path
}

export function peekPendingNotificationDestination(): string | null {
  const now = Date.now()
  if (pendingPath) {
    if (pendingExpiresAt && now > pendingExpiresAt) {
      clearMemoryPending()
      persistPending(null)
    } else {
      return pendingPath
    }
  }
  return readPersistedPending()
}

/**
 * Drop queued destinations on logout / account switch so the next user cannot
 * inherit another account's notification target.
 */
export function clearPendingNotificationDestination(): void {
  clearMemoryPending()
  persistPending(null)
}

/** Test helper — clear module state between unit tests. */
export function _resetNotificationNavigationForTests(): void {
  clearMemoryPending()
  lastNavigatedPath = null
  lastNavigatedAt = 0
  ready = false
  persistPending(null)
}
