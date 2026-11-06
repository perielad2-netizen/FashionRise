import { apiRequest } from '@/services/api/client'
import { tokenStore, type StoredTokens } from '@/services/auth/tokenStore'

export type User = {
  id: string
  email: string
  username: string
  is_active: boolean
  is_admin: boolean
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
  invitationCode: string
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

export async function getCfAccessSsoStatus(signal?: AbortSignal): Promise<CfAccessSsoStatus> {
  return apiRequest<CfAccessSsoStatus>('/auth/cf-access/status', {
    method: 'GET',
    auth: false,
    signal,
  })
}

/**
 * Seamless login using the Cloudflare Access JWT that the edge forwards to origin.
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

export async function register(
  payload: RegisterPayload,
): Promise<{ user: User; tokens: StoredTokens }> {
  // Clear any previous session before accepting a newly created account.
  tokenStore.clear()
  const tokens = await apiRequest<TokenResponse>('/auth/register', {
    method: 'POST',
    body: {
      email: payload.email.trim().toLowerCase(),
      username: payload.username.trim(),
      password: payload.password,
      display_name: payload.displayName ?? null,
      invitation_code: payload.invitationCode.trim(),
    },
    auth: false,
  })
  const stored = toStored(tokens)
  tokenStore.set(stored)
  try {
    const user = await fetchMe()
    return { user, tokens: stored }
  } catch (err) {
    // Registration may have committed, but identity bootstrap failed. Drop the
    // half-session so no stale prior account remains; recover via sign-in.
    tokenStore.clear()
    throw err
  }
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
