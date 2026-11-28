/**
 * Extract the push destination URL from Capacitor notification events.
 *
 * Android FCM (flat extras) and iOS APNs (userInfo including nested `aps`) do
 * not expose identical shapes — never assume `notification.data.url` alone.
 *
 * Only **explicit destination fields** are read (`url` / `path` / `link` at the
 * data root, under nested `data`, or `notification.link`). Arbitrary userInfo
 * string keys are never scanned.
 */

type NotificationLike = {
  data?: Record<string, unknown> | null
  link?: unknown
}

function asNonEmptyString(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

/**
 * Destination from a Cap `pushNotificationActionPerformed` notification.
 * Returns the raw candidate string (may be absolute or relative); caller sanitizes.
 */
export function extractNotificationDestinationUrl(
  notification: NotificationLike | null | undefined,
): string | null {
  if (!notification) return null
  const data = (notification.data || {}) as Record<string, unknown>

  const candidates: unknown[] = [data.url, data.path, data.link, notification.link]

  const nested = data.data
  if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
    const bag = nested as Record<string, unknown>
    candidates.push(bag.url, bag.path, bag.link)
  }

  for (const c of candidates) {
    const hit = asNonEmptyString(c)
    if (hit) return hit
  }

  return null
}
