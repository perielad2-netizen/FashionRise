import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const platform = vi.hoisted(() => ({
  isNativeShell: vi.fn(() => false),
  nativePlatform: vi.fn(() => 'web' as 'web' | 'ios' | 'android'),
}))

vi.mock('@/services/native/platform', () => ({
  isNativeShell: () => platform.isNativeShell(),
  nativePlatform: () => platform.nativePlatform(),
}))

vi.mock('@/services/native/iap', () => ({
  isNativeIosStarsShop: () => false,
  recoverPendingStarsPurchases: vi.fn(),
}))

vi.mock('@/services/native/nativePush', () => ({
  clearNativePushForLogout: vi.fn(async () => undefined),
  syncNativePushAfterAuth: vi.fn(async () => 'disabled' as const),
}))

vi.mock('@/services/auth/authApi', () => ({
  login: vi.fn(),
  register: vi.fn(),
  restoreSession: vi.fn(async () => null),
  logoutLocal: vi.fn(),
  fetchMe: vi.fn(),
  getGoogleOAuthStatus: async () => ({ google_oauth_enabled: true }),
  getRegistrationStatus: async () => ({
    mode: 'public',
    configured_mode: 'public',
    registration_available: true,
    requires_invitation: false,
    requires_email_verification: false,
    email_delivery_configured: false,
  }),
  getPasswordResetStatus: async () => ({
    password_reset_available: false,
    password_reset_enabled: false,
    email_delivery_configured: false,
  }),
}))

vi.mock('@/services/auth/tokenStore', () => ({
  tokenStore: { get: () => null, set: vi.fn(), clear: vi.fn() },
}))

vi.mock('@/lib/fabricAssetCache', () => ({
  bindFabricCacheToUser: vi.fn(),
}))

vi.mock('@/services/competitionsApi', () => ({
  postStreakCheckIn: vi.fn(async () => ({
    current_streak: 0,
    last_checkin_date: null,
    lifetime_checkins: 0,
    days_until_reward: 7,
    rewarded_this_checkin: false,
    stars_awarded: 0,
    reward_every_days: 7,
    reward_stars: 10,
    rewards_enabled: false,
  })),
}))

import { AuthProvider, useAuth } from '@/services/auth/AuthProvider'

function Probe() {
  const { googleOAuthAvailable, bootstrapping } = useAuth()
  if (bootstrapping) return <div data-testid="boot">boot</div>
  return <div data-testid="google">{googleOAuthAvailable ? 'on' : 'off'}</div>
}

describe('AuthProvider Google Sign-In gate (Guideline 4.8)', () => {
  beforeEach(() => {
    platform.isNativeShell.mockReset()
    platform.nativePlatform.mockReset()
  })

  it('keeps Google available on web when backend OAuth is enabled', async () => {
    platform.isNativeShell.mockReturnValue(false)
    platform.nativePlatform.mockReturnValue('web')
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )
    await waitFor(() => expect(screen.getByTestId('google').textContent).toBe('on'))
  })

  it('hides Google on iOS native shell even when backend OAuth is enabled', async () => {
    platform.isNativeShell.mockReturnValue(true)
    platform.nativePlatform.mockReturnValue('ios')
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )
    await waitFor(() => expect(screen.getByTestId('google').textContent).toBe('off'))
  })
})
