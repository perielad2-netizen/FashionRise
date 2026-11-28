/**
 * Extract the push destination URL from Capacitor notification events.
 *
 * Android FCM (flat extras) and iOS APNs (userInfo including nested `aps`) do
 * not expose identical shapes — never assume `notification.data.url` alone.
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

function pushCandidate(value: unknown): string | null {
  const s = asNonEmptyString(value)
  if (!s) return null
  // Prefer studio/privacy destinations; still return other strings for sanitizer.
  return s
}

/**
 * Best-effort destination from a Cap `pushNotificationActionPerformed` notification.
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
    const hit = pushCandidate(c)
    if (hit) return hit
  }

  // iOS userInfo may leave custom keys beside `aps`; scan string values once.
  for (const [key, value] of Object.entries(data)) {
    if (key === 'aps' || key === 'data') continue
    const hit = pushCandidate(value)
    if (hit && (hit.startsWith('/') || hit.startsWith('http'))) return hit
  }

  return null
}
