import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiRequest = vi.fn()
const platform = vi.hoisted(() => ({
  isNativeShell: vi.fn(() => true),
  nativePlatform: vi.fn(() => 'android' as 'android' | 'ios' | 'web'),
}))

vi.mock('@/services/api/client', () => ({
  apiRequest: (...args: unknown[]) => apiRequest(...args),
  getApiBaseUrl: () => 'https://fashionrise.app/api/v1',
}))

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
  })

  it('returns registration_failed when no FCM token arrives', async () => {
    _setNativePushRegTimeoutForTests(50)
    apiRequest.mockResolvedValueOnce({ android_enabled: true, ios_enabled: false })
    const { PushNotifications } = await import('@capacitor/push-notifications')
    vi.mocked(PushNotifications.register).mockResolvedValueOnce(undefined)
    // Token stays empty; registration listener never fires in mock.
    const result = await syncNativePushAfterAuth()
    expect(result).toBe('registration_failed')
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
