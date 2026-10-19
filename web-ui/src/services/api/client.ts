import { tokenStore } from '@/services/auth/tokenStore'

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

type RequestOptions = {
  method?: string
  body?: unknown
  auth?: boolean
  signal?: AbortSignal
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
  }

  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  if (options.auth !== false) {
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
    if (typeof detail === 'string' && detail.trim()) return detail
    if (typeof detail === 'object' && detail !== null && 'message' in detail) {
      const message = (detail as { message: unknown }).message
      if (typeof message === 'string' && message.trim()) return message
    }
  }
  return friendlyStatus(status)
}

function friendlyStatus(status: number): string {
  if (status === 401) return 'Invalid email or password.'
  if (status === 409) return 'Draft was updated elsewhere. Resolve the conflict before saving again.'
  if (status === 422) return 'Please check your email and password.'
  if (status >= 500) return 'FashionRise is temporarily unavailable. Try again shortly.'
  return 'Something went wrong. Please try again.'
}
