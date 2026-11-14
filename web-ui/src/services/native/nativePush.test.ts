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
    removeAllListeners: vi.fn(async () => undefined),
  },
}))

import {
  _resetNativePushListenersForTests,
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

  it('registers after auth when Android is enabled', async () => {
    apiRequest.mockResolvedValueOnce({ android_enabled: true, ios_enabled: false })
    localStorage.setItem('fr.nativePush.token', 'fcm-token-abcdefghijklmnopqrstuv')
    apiRequest.mockResolvedValueOnce({
      id: '1',
      platform: 'android',
      created_at: '2026-11-13T00:00:00Z',
      updated_at: '2026-11-13T00:00:00Z',
    })
    const result = await syncNativePushAfterAuth()
    expect(result).toBe('granted')
    expect(apiRequest).toHaveBeenCalledWith(
      '/push/native/devices',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('respects desired=false without prompting', async () => {
    setNativePushDesired(false)
    const result = await syncNativePushAfterAuth()
    expect(result).toBe('skipped')
    expect(apiRequest).not.toHaveBeenCalled()
  })
})
