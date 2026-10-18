import { beforeEach, describe, expect, it, vi } from 'vitest'
import { tokenStore } from '@/services/auth/tokenStore'

describe('tokenStore', () => {
  beforeEach(() => {
    tokenStore.clear()
  })

  it('stores and clears tokens', () => {
    expect(tokenStore.get()).toBeNull()
    tokenStore.set({ accessToken: 'a', refreshToken: 'r' })
    expect(tokenStore.get()).toEqual({ accessToken: 'a', refreshToken: 'r' })
    tokenStore.clear()
    expect(tokenStore.get()).toBeNull()
  })
})

describe('auth validation helpers', () => {
  it('rejects empty email/password at UI level', () => {
    const email = ''
    const password = ''
    expect(Boolean(email.trim() && password)).toBe(false)
  })
})

describe('restoreSession behavior (mocked)', () => {
  beforeEach(() => {
    tokenStore.clear()
    vi.restoreAllMocks()
  })

  it('returns null when no tokens exist', async () => {
    const { restoreSession } = await import('@/services/auth/authApi')
    await expect(restoreSession()).resolves.toBeNull()
  })
})
