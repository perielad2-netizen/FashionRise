import { apiRequest, getApiBaseUrl } from '@/services/api/client'
import { tokenStore, type StoredTokens } from '@/services/auth/tokenStore'

export type User = {
  id: string
  email: string
  username: string
  is_active: boolean
  is_admin: boolean
  /** AI Stars balance (Magic spend). */
  ai_stars?: number
  /** Owner accounts never debit Stars. */
  ai_stars_unlimited?: boolean
  created_at: string
}

export type TokenResponse = {
  access_token: string
  refresh_token: string
  token_type: string
}

export type LoginPayload = {
  email: string
  password: string
}

export type RegisterPayload = {
  email: string
  username: string
  password: string
  displayName?: string | null
  invitationCode?: string | null
}

export type RegisterResult =
  | { status: 'authenticated'; user: User; tokens: StoredTokens }
  | { status: 'verification_pending'; email: string; message: string }

export type RegistrationStatus = {
  mode: 'closed' | 'invite_only' | 'public'
  configured_mode: 'closed' | 'invite_only' | 'public'
  registration_available: boolean
  requires_invitation: boolean
  requires_email_verification: boolean
  email_delivery_configured: boolean
  prerequisite?: string | null
  note?: string | null
}

function toStored(tokens: TokenResponse): StoredTokens {
  return {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
  }
}

export type CfAccessSsoStatus = {
  sso_enabled: boolean
  note?: string
}

export type GoogleOAuthStatus = {
  google_oauth_enabled: boolean
  auto_register?: boolean
  note?: string
}

export async function getCfAccessSsoStatus(signal?: AbortSignal): Promise<CfAccessSsoStatus> {
  return apiRequest<CfAccessSsoStatus>('/auth/cf-access/status', {
    method: 'GET',
    auth: false,
    signal,
  })
}

export async function getGoogleOAuthStatus(signal?: AbortSignal): Promise<GoogleOAuthStatus> {
  return apiRequest<GoogleOAuthStatus>('/auth/google/status', {
    method: 'GET',
    auth: false,
    signal,
  })
}

export async function getRegistrationStatus(signal?: AbortSignal): Promise<RegistrationStatus> {
  return apiRequest<RegistrationStatus>('/auth/registration/status', {
    method: 'GET',
    auth: false,
    signal,
  })
}

/** Browser navigation target that begins Google Sign-In (server redirects to Google). */
export function getGoogleOAuthStartUrl(
  nextPath = '/studio/home',
  opts?: { client?: 'web' | 'android' },
): string {
  const base = getApiBaseUrl()
  const next = nextPath.startsWith('/') && !nextPath.startsWith('//') ? nextPath : '/studio/home'
  const client = opts?.client === 'android' ? 'android' : 'web'
  const qs = new URLSearchParams({ next, client })
  return `${base}/auth/google/start?${qs.toString()}`
}

/**
 * Apply tokens returned from the Google OAuth complete redirect (hash fragment)
 * or Android native handoff redeem.
 */
export async function completeGoogleOAuthSession(tokens: {
  access_token: string
  refresh_token: string
}): Promise<{ user: User; tokens: StoredTokens }> {
  tokenStore.clear()
  const stored = toStored({
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
    token_type: 'bearer',
  })
  tokenStore.set(stored)
  try {
    const user = await fetchMe()
    return { user, tokens: stored }
  } catch (err) {
    tokenStore.clear()
    throw err
  }
}

/** Redeem one-time Android OAuth handoff code (tokens never appear in the deep link). */
export async function redeemGoogleNativeHandoff(code: string): Promise<{
  access_token: string
  refresh_token: string
}> {
  return apiRequest<TokenResponse>('/auth/google/native-handoff', {
    method: 'POST',
    body: { code },
    auth: false,
  })
}

/**
 * Legacy Cloudflare Access seamless login (kept for rollback; prefer Google OAuth).
 * Maps verified Access email → existing FashionRise user only (never invents accounts).
 */
export async function loginWithCloudflareAccess(): Promise<{ user: User; tokens: StoredTokens }> {
  tokenStore.clear()
  const tokens = await apiRequest<TokenResponse>('/auth/cf-access/login', {
    method: 'POST',
    auth: false,
  })
  const stored = toStored(tokens)
  tokenStore.set(stored)
  try {
    const user = await fetchMe()
    return { user, tokens: stored }
  } catch (err) {
    tokenStore.clear()
    throw err
  }
}

export async function login(payload: LoginPayload): Promise<{ user: User; tokens: StoredTokens }> {
  // Drop any prior tokens before applying a new session (account switch).
  tokenStore.clear()
  const tokens = await apiRequest<TokenResponse>('/auth/login', {
    method: 'POST',
    body: {
      email: payload.email.trim().toLowerCase(),
      password: payload.password,
    },
    auth: false,
  })
  const stored = toStored(tokens)
  tokenStore.set(stored)
  try {
    const user = await fetchMe()
    return { user, tokens: stored }
  } catch (err) {
    tokenStore.clear()
    throw err
  }
}

export async function register(payload: RegisterPayload): Promise<RegisterResult> {
  // Clear any previous session before accepting a newly created account.
  tokenStore.clear()
  const invite = (payload.invitationCode || '').trim()
  const response = await apiRequest<{
    status: 'authenticated' | 'verification_pending'
    access_token?: string | null
    refresh_token?: string | null
    token_type?: string
    email?: string | null
    message?: string | null
  }>('/auth/register', {
    method: 'POST',
    body: {
      email: payload.email.trim().toLowerCase(),
      username: payload.username.trim(),
      password: payload.password,
      display_name: payload.displayName ?? null,
      invitation_code: invite || null,
    },
    auth: false,
  })

  if (response.status === 'verification_pending') {
    return {
      status: 'verification_pending',
      email: (response.email || payload.email).trim().toLowerCase(),
      message:
        response.message ||
        'Check your email to verify your account before signing in.',
    }
  }

  if (!response.access_token || !response.refresh_token) {
    throw new Error('Registration did not return a session')
  }

  const stored = toStored({
    access_token: response.access_token,
    refresh_token: response.refresh_token,
    token_type: response.token_type || 'bearer',
  })
  tokenStore.set(stored)
  try {
    const user = await fetchMe()
    return { status: 'authenticated', user, tokens: stored }
  } catch (err) {
    // Registration may have committed, but identity bootstrap failed. Drop the
    // half-session so no stale prior account remains; recover via sign-in.
    tokenStore.clear()
    throw err
  }
}

export async function verifyEmail(token: string): Promise<{ user: User; tokens: StoredTokens }> {
  tokenStore.clear()
  const tokens = await apiRequest<TokenResponse>('/auth/verify-email', {
    method: 'POST',
    body: { token: token.trim() },
    auth: false,
  })
  const stored = toStored(tokens)
  tokenStore.set(stored)
  try {
    const user = await fetchMe()
    return { user, tokens: stored }
  } catch (err) {
    tokenStore.clear()
    throw err
  }
}

export async function resendVerification(email: string): Promise<void> {
  await apiRequest<void>('/auth/resend-verification', {
    method: 'POST',
    body: { email: email.trim().toLowerCase() },
    auth: false,
  })
}

export async function fetchMe(): Promise<User> {
  return apiRequest<User>('/auth/me')
}

export async function refreshSession(): Promise<StoredTokens> {
  const current = tokenStore.get()
  if (!current?.refreshToken) {
    throw new Error('No refresh token')
  }
  const tokens = await apiRequest<TokenResponse>('/auth/refresh', {
    method: 'POST',
    body: { refresh_token: current.refreshToken },
    auth: false,
  })
  const stored = toStored(tokens)
  tokenStore.set(stored)
  return stored
}

export function logoutLocal(): void {
  tokenStore.clear()
}

/** Permanently delete the signed-in account. Caller must clear local session after. */
export async function deleteAccount(): Promise<void> {
  await apiRequest<void>('/auth/account', {
    method: 'DELETE',
    body: { confirm: 'DELETE' },
  })
  tokenStore.clear()
}

/** Validate existing session: /auth/me, refresh once on 401. */
export async function restoreSession(): Promise<User | null> {
  const tokens = tokenStore.get()
  if (!tokens) return null

  try {
    return await fetchMe()
  } catch (err) {
    const status = typeof err === 'object' && err && 'status' in err ? Number(err.status) : 0
    if (status !== 401) {
      tokenStore.clear()
      return null
    }
    try {
      await refreshSession()
      return await fetchMe()
    } catch {
      tokenStore.clear()
      return null
    }
  }
}
