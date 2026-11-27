import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiRequest = vi.fn()
const platform = vi.hoisted(() => ({
  isNativeShell: vi.fn(() => true),
  nativePlatform: vi.fn(() => 'android' as 'android' | 'ios' | 'web'),
}))

vi.mock('@/services/api/client', () => {
  class ApiError extends Error {
    status: number
    body: unknown
    constructor(message: string, status: number, body: unknown) {
      super(message)
      this.name = 'ApiError'
      this.status = status
      this.body = body
    }
  }
  return {
    ApiError,
    apiRequest: (...args: unknown[]) => apiRequest(...args),
    getApiBaseUrl: () => 'https://fashionrise.app/api/v1',
  }
})

vi.mock('@/services/native/platform', () => ({
  isNativeShell: () => platform.isNativeShell(),
  nativePlatform: () => platform.nativePlatform(),
}))

vi.mock('@/services/auth/tokenStore', () => ({
  tokenStore: {
    get: () => ({ accessToken: 'access', refreshToken: 'refresh' }),
  },
}))

vi.mock('@capacitor/push-notifications', () => ({
  PushNotifications: {
    addListener: vi.fn(async () => ({ remove: vi.fn() })),
    checkPermissions: vi.fn(async () => ({ receive: 'granted' })),
    requestPermissions: vi.fn(async () => ({ receive: 'granted' })),
    register: vi.fn(async () => undefined),
    createChannel: vi.fn(async () => undefined),
    removeAllListeners: vi.fn(async () => undefined),
  },
}))

import {
  _resetNativePushListenersForTests,
  _setNativePushRegTimeoutForTests,
  enableNativePush,
  formatNativePushRegistrationFailureMessage,
  getLastNativePushDiagnostic,
  nativePushIsEnabled,
  setNativePushDesired,
  syncNativePushAfterAuth,
} from './nativePush'

describe('nativePush', () => {
  beforeEach(() => {
    apiRequest.mockReset()
    _resetNativePushListenersForTests()
    setNativePushDesired(true)
    platform.isNativeShell.mockReturnValue(true)
    platform.nativePlatform.mockReturnValue('android')
    localStorage.clear()
  })

  it('skips registration when platform capability is disabled', async () => {
    apiRequest.mockResolvedValueOnce({ android_enabled: false, ios_enabled: false })
    const result = await syncNativePushAfterAuth()
    expect(result).toBe('disabled')
    expect(apiRequest).toHaveBeenCalledWith('/push/native/capability', { auth: false })
    expect(getLastNativePushDiagnostic()?.stage).toBe('capability')
  })

  it('auto-registers when OS permission is already granted (no second activation)', async () => {
    const token = 'fcm-token-abcdefghijklmnopqrstuv'
    localStorage.setItem('fr.nativePush.token', token)
    apiRequest
      .mockResolvedValueOnce({ android_enabled: true, ios_enabled: false }) // capability
      .mockResolvedValueOnce({
        id: '1',
        platform: 'android',
        device_token: token,
        created_at: '2026-11-13T00:00:00Z',
        updated_at: '2026-11-13T00:00:00Z',
      }) // POST register
      .mockResolvedValueOnce([
        {
          id: '1',
          platform: 'android',
          device_token: token,
          created_at: '2026-11-13T00:00:00Z',
          updated_at: '2026-11-13T00:00:00Z',
        },
      ]) // GET confirm
    const result = await syncNativePushAfterAuth()
    expect(result).toBe('granted')
    expect(apiRequest).toHaveBeenCalledWith(
      '/push/native/devices',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(apiRequest).toHaveBeenCalledWith('/push/native/devices')
    expect(getLastNativePushDiagnostic()?.stage).toBe('ok')
    expect(getLastNativePushDiagnostic()?.tokenFingerprint).toMatch(/^fcm-…/)
  })

  it('returns registration_failed when no FCM token arrives and records token_timeout', async () => {
    _setNativePushRegTimeoutForTests(50)
    apiRequest.mockResolvedValue({ android_enabled: true, ios_enabled: false })
    const { PushNotifications } = await import('@capacitor/push-notifications')
    vi.mocked(PushNotifications.register).mockResolvedValue(undefined)
    // Token stays empty; registration listener never fires in mock.
    const result = await syncNativePushAfterAuth()
    expect(result).toBe('registration_failed')
    expect(getLastNativePushDiagnostic()?.stage).toBe('token_timeout')
    expect(formatNativePushRegistrationFailureMessage()).toMatch(/FCM token timed out/i)
    // Never reached backend register.
    expect(apiRequest.mock.calls.some((c) => c[0] === '/push/native/devices')).toBe(false)
  })

  it('surfaces registrationError stage with actionable copy (no full token leakage)', async () => {
    _setNativePushRegTimeoutForTests(50)
    apiRequest.mockResolvedValue({ android_enabled: true, ios_enabled: false })
    const { PushNotifications } = await import('@capacitor/push-notifications')
    const listeners: Record<string, (payload: unknown) => void> = {}
    vi.mocked(PushNotifications.addListener).mockImplementation(async (event, cb) => {
      listeners[event] = cb as (payload: unknown) => void
      return { remove: vi.fn() }
    })
    vi.mocked(PushNotifications.register).mockImplementation(async () => {
      listeners.registrationError?.({
        error: 'SERVICE_NOT_AVAILABLE longtoken_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_secret',
      })
    })
    const result = await syncNativePushAfterAuth()
    expect(result).toBe('registration_failed')
    expect(getLastNativePushDiagnostic()?.stage).toBe('token_error')
    const msg = formatNativePushRegistrationFailureMessage()
    expect(msg).toMatch(/FCM token/i)
    expect(msg).not.toMatch(/ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/)
    expect(getLastNativePushDiagnostic()?.message).toContain('[redacted]')
  })

  it('manual enableNativePush shares syncNativePushAfterAuth implementation', async () => {
    const token = 'fcm-token-abcdefghijklmnopqrstuv'
    localStorage.setItem('fr.nativePush.token', token)
    apiRequest
      .mockResolvedValueOnce({ android_enabled: true, ios_enabled: false })
      .mockResolvedValueOnce({
        id: '1',
        platform: 'android',
        device_token: token,
        created_at: '2026-11-13T00:00:00Z',
        updated_at: '2026-11-13T00:00:00Z',
      })
      .mockResolvedValueOnce([
        {
          id: '1',
          platform: 'android',
          device_token: token,
          created_at: '2026-11-13T00:00:00Z',
          updated_at: '2026-11-13T00:00:00Z',
        },
      ])
    await expect(enableNativePush()).resolves.toBe('granted')
  })

  it('records backend_post when device POST fails after token', async () => {
    const { ApiError } = await import('@/services/api/client')
    const token = 'fcm-token-abcdefghijklmnopqrstuv'
    localStorage.setItem('fr.nativePush.token', token)
    apiRequest
      .mockResolvedValueOnce({ android_enabled: true, ios_enabled: false })
      .mockRejectedValueOnce(new ApiError('server error', 500, null))
    const result = await syncNativePushAfterAuth()
    expect(result).toBe('registration_failed')
    expect(getLastNativePushDiagnostic()?.stage).toBe('backend_post')
    expect(getLastNativePushDiagnostic()?.code).toBe('post_failed_500')
    expect(formatNativePushRegistrationFailureMessage()).toMatch(/server rejected/i)
  })

  it('does not tell the user to sign in again for gateway HTTP 403', async () => {
    const { ApiError } = await import('@/services/api/client')
    const token = 'fcm-token-abcdefghijklmnopqrstuv'
    localStorage.setItem('fr.nativePush.token', token)
    apiRequest
      .mockResolvedValueOnce({ android_enabled: true, ios_enabled: false })
      .mockRejectedValueOnce(new ApiError('Forbidden', 403, null))
    const result = await syncNativePushAfterAuth()
    expect(result).toBe('registration_failed')
    expect(getLastNativePushDiagnostic()?.code).toBe('post_failed_403')
    const msg = formatNativePushRegistrationFailureMessage()
    expect(msg).toMatch(/HTTP 403/i)
    expect(msg).toMatch(/signing in again will not help/i)
    expect(msg).not.toMatch(/Sign in again and retry/i)
  })

  it('asks to sign in again only for HTTP 401 on device POST', async () => {
    const { ApiError } = await import('@/services/api/client')
    const token = 'fcm-token-abcdefghijklmnopqrstuv'
    localStorage.setItem('fr.nativePush.token', token)
    apiRequest
      .mockResolvedValueOnce({ android_enabled: true, ios_enabled: false })
      .mockRejectedValueOnce(new ApiError('Your session expired. Please sign in again.', 401, null))
    await expect(syncNativePushAfterAuth()).resolves.toBe('registration_failed')
    expect(formatNativePushRegistrationFailureMessage()).toMatch(/Sign in again and retry/i)
  })

  it('respects desired=false without prompting', async () => {
    setNativePushDesired(false)
    const result = await syncNativePushAfterAuth()
    expect(result).toBe('skipped')
    expect(apiRequest).not.toHaveBeenCalled()
  })

  it('does not report enabled from local token alone without backend registration', async () => {
    localStorage.setItem('fr.nativePush.token', 'fcm-token-abcdefghijklmnopqrstuv')
    apiRequest
      .mockResolvedValueOnce({ android_enabled: true, ios_enabled: false })
      .mockResolvedValueOnce([]) // no devices on backend
    expect(await nativePushIsEnabled()).toBe(false)
  })

  it('reports enabled only when backend has this account device token', async () => {
    const token = 'fcm-token-abcdefghijklmnopqrstuv'
    localStorage.setItem('fr.nativePush.token', token)
    apiRequest
      .mockResolvedValueOnce({ android_enabled: true, ios_enabled: false })
      .mockResolvedValueOnce([
        {
          id: '1',
          platform: 'android',
          device_token: token,
          created_at: '2026-11-13T00:00:00Z',
          updated_at: '2026-11-13T00:00:00Z',
        },
      ])
    expect(await nativePushIsEnabled()).toBe(true)
  })
})
