import { tokenStore, type StoredTokens } from '@/services/auth/tokenStore'

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(message: string, status: number, body: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

export function getApiBaseUrl(): string {
  const raw = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (!raw || !raw.trim()) {
    throw new Error('VITE_API_BASE_URL is not configured')
  }
  return raw.replace(/\/$/, '')
}

/** Fired when refresh fails and the local session is cleared (V2-0012/0013). */
export const SESSION_EXPIRED_EVENT = 'fr:session-expired'

type RequestOptions = {
  method?: string
  body?: unknown
  auth?: boolean
  signal?: AbortSignal
  /** Internal: skip one-shot refresh retry (already retried). */
  _retriedAfterRefresh?: boolean
}

type TokenResponse = {
  access_token: string
  refresh_token: string
  token_type: string
}

let refreshInFlight: Promise<boolean> | null = null

function notifySessionExpired(): void {
  try {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT))
    }
  } catch {
    /* ignore */
  }
}

/** True when the store still holds the exact session that started a refresh. */
function sessionStillMatches(started: StoredTokens): boolean {
  const now = tokenStore.get()
  return Boolean(
    now &&
      now.refreshToken === started.refreshToken &&
      now.accessToken === started.accessToken,
  )
}

/**
 * Single-flight access-token refresh using the stored refresh token.
 * Does not import authApi (avoids circular dependency with apiRequest).
 *
 * If logout or account-switch changes the store while the refresh HTTP call is
 * in flight, the response is discarded — never restore old tokens, clear a
 * newer session, or apply tokens for a different account.
 */
export async function refreshAccessToken(): Promise<boolean> {
  const current = tokenStore.get()
  if (!current?.refreshToken) return false
  if (refreshInFlight) return refreshInFlight

  const started: StoredTokens = {
    accessToken: current.accessToken,
    refreshToken: current.refreshToken,
  }

  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${getApiBaseUrl()}/auth/refresh`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: started.refreshToken }),
      })
      const text = await response.text()
      let parsed: unknown = null
      if (text) {
        try {
          parsed = JSON.parse(text)
        } catch {
          parsed = text
        }
      }
      // Logout / switch while in flight: discard without mutating the new session.
      if (!sessionStillMatches(started)) return false
      if (!response.ok) return false
      const body = parsed as TokenResponse
      if (!body?.access_token || !body?.refresh_token) return false
      // Re-check after parsing — another writer may have landed between.
      if (!sessionStillMatches(started)) return false
      const stored: StoredTokens = {
        accessToken: body.access_token,
        refreshToken: body.refresh_token,
      }
      tokenStore.set(stored)
      return true
    } catch {
      return false
    } finally {
      refreshInFlight = null
    }
  })()

  return refreshInFlight
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
  }

  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  const useAuth = options.auth !== false
  if (useAuth) {
    const tokens = tokenStore.get()
    if (tokens?.accessToken) {
      headers.Authorization = `Bearer ${tokens.accessToken}`
    }
  }

  let response: Response
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      method: options.method ?? (options.body !== undefined ? 'POST' : 'GET'),
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    })
  } catch {
    throw new ApiError('Unable to reach FashionRise. Check that the API is running.', 0, null)
  }

  // Mid-session access expiry (V2-0012 / V2-0013): refresh once, then retry.
  const tokensAt401 = useAuth ? tokenStore.get() : null
  if (
    response.status === 401 &&
    useAuth &&
    !options._retriedAfterRefresh &&
    Boolean(tokensAt401?.refreshToken)
  ) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      return apiRequest<T>(path, { ...options, _retriedAfterRefresh: true })
    }
    // Only clear the session that failed. Logout / account-switch may have
    // already replaced or removed tokens while refresh was in flight.
    if (tokensAt401 && sessionStillMatches(tokensAt401)) {
      tokenStore.clear()
      notifySessionExpired()
    }
    throw new ApiError('Your session expired. Please sign in again.', 401, null)
  }

  const text = await response.text()
  let parsed: unknown = null
  if (text) {
    try {
      parsed = JSON.parse(text)
    } catch {
      parsed = text
    }
  }

  if (!response.ok) {
    throw new ApiError(extractErrorMessage(parsed, response.status), response.status, parsed)
  }

  return parsed as T
}

function extractErrorMessage(parsed: unknown, status: number): string {
  if (typeof parsed === 'object' && parsed !== null && 'detail' in parsed) {
    const detail = (parsed as { detail: unknown }).detail
    if (typeof detail === 'string' && detail.trim()) {
      // Prefer actionable copy for mid-session auth failures (before refresh existed).
      if (status === 401 && /invalid token/i.test(detail)) {
        return 'Your session expired. Please sign in again.'
      }
      return detail
    }
    if (typeof detail === 'object' && detail !== null && 'message' in detail) {
      const message = (detail as { message: unknown }).message
      if (typeof message === 'string' && message.trim()) return message
    }
    // FastAPI validation errors: [{ loc, msg, type }, ...]
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0]
      if (typeof first === 'object' && first !== null && 'msg' in first) {
        const msg = (first as { msg: unknown }).msg
        if (typeof msg === 'string' && msg.trim()) return msg
      }
    }
  }
  return friendlyStatus(status)
}

function friendlyStatus(status: number): string {
  if (status === 401) return 'Your session expired. Please sign in again.'
  if (status === 403) {
    return 'This action isn’t available right now. Your sketch is unchanged — please try again shortly.'
  }
  if (status === 409) return 'Draft was updated elsewhere. Resolve the conflict before saving again.'
  // Auth forms historically used 422 for bad credentials; elsewhere it means invalid input.
  if (status === 422) return 'Please check your input and try again.'
  if (status >= 500) return 'FashionRise is temporarily unavailable. Try again shortly.'
  return 'Something went wrong. Please try again.'
}
