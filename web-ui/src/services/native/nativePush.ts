/**
 * Native push (FCM / APNs) via @capacitor/push-notifications.
 *
 * Fail-closed: registration only runs when the authenticated API reports
 * platform enablement. Web Push (VAPID) stays unchanged for browser users.
 * Never request permission before auth; never register before auth.
 *
 * If OS permission is already granted and the user has not opted out, we
 * automatically obtain + register the FCM/APNs token after login / resume.
 * Settings is preference/visibility — not a mandatory second activation.
 * "Enabled" requires successful backend registration for this account+device.
 */
import { PushNotifications } from '@capacitor/push-notifications'
import { apiRequest, getApiBaseUrl } from '@/services/api/client'
import { tokenStore } from '@/services/auth/tokenStore'
import { isNativeShell, nativePlatform } from './platform'
import { sanitizePushDestination } from './pushDestination'
import { navigateInApp } from './urlPolicy'

export type NativePushCapability = {
  android_enabled: boolean
  ios_enabled: boolean
}

export type NativePushDeviceRow = {
  id: string
  platform: 'android' | 'ios'
  device_token: string
  created_at: string
  updated_at: string
}

export type NativePushSyncResult =
  | 'granted'
  | 'denied'
  | 'unsupported'
  | 'disabled'
  | 'skipped'
  | 'unauthenticated'
  | 'registration_failed'

const TOKEN_KEY = 'fr.nativePush.token'
const PLATFORM_KEY = 'fr.nativePush.platform'
const DESIRED_KEY = 'fr.nativePush.desired'
let regTimeoutMs = 20_000

let listenersInstalled = false
let lastRegistrationError: string | null = null
let tokenWaiters: Array<(token: string | null) => void> = []
let syncInFlight: Promise<NativePushSyncResult> | null = null

function platformForApi(): 'android' | 'ios' | null {
  const p = nativePlatform()
  if (p === 'android' || p === 'ios') return p
  return null
}

export function isNativePushDesired(): boolean {
  if (typeof window === 'undefined') return true
  try {
    const raw = localStorage.getItem(DESIRED_KEY)
    if (raw === null) return true
    return raw !== '0' && raw !== 'false'
  } catch {
    return true
  }
}

export function setNativePushDesired(desired: boolean): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(DESIRED_KEY, desired ? '1' : '0')
  } catch {
    /* private mode */
  }
}

function readStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function writeStoredToken(token: string | null, platform: string | null): void {
  try {
    if (!token) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(PLATFORM_KEY)
      return
    }
    localStorage.setItem(TOKEN_KEY, token)
    if (platform) localStorage.setItem(PLATFORM_KEY, platform)
  } catch {
    /* ignore */
  }
}

function resolveTokenWaiters(token: string | null): void {
  const waiters = tokenWaiters
  tokenWaiters = []
  for (const resolve of waiters) resolve(token)
}

function waitForDeviceToken(timeoutMs = regTimeoutMs): Promise<string | null> {
  const existing = readStoredToken()
  if (existing) return Promise.resolve(existing)
  return new Promise((resolve) => {
    const timer = window.setTimeout(() => {
      tokenWaiters = tokenWaiters.filter((w) => w !== onToken)
      resolve(readStoredToken())
    }, timeoutMs)
    const onToken = (token: string | null) => {
      window.clearTimeout(timer)
      resolve(token)
    }
    tokenWaiters.push(onToken)
  })
}

export async function getNativePushCapability(): Promise<NativePushCapability> {
  return apiRequest<NativePushCapability>('/push/native/capability', { auth: false })
}

export async function listNativePushDevices(): Promise<NativePushDeviceRow[]> {
  return apiRequest<NativePushDeviceRow[]>('/push/native/devices')
}

export async function registerNativePushDevice(input: {
  platform: 'android' | 'ios'
  device_token: string
  app_version?: string
}): Promise<NativePushDeviceRow> {
  return apiRequest<NativePushDeviceRow>('/push/native/devices', {
    method: 'POST',
    body: input,
  })
}

export async function deleteNativePushDevice(deviceToken: string): Promise<void> {
  await apiRequest<void>('/push/native/devices', {
    method: 'DELETE',
    body: { device_token: deviceToken },
  })
}

function openNotificationUrl(rawUrl: unknown): void {
  // Push taps never open reset/verify/OAuth or any token-bearing URL.
  navigateInApp(sanitizePushDestination(rawUrl))
}

const ANDROID_CHANNEL_ID = 'fashionrise_social'

async function ensureAndroidChannels(): Promise<void> {
  if (platformForApi() !== 'android') return
  try {
    await PushNotifications.createChannel({
      id: ANDROID_CHANNEL_ID,
      name: 'FashionRise social',
      description: 'Likes, comments, follows, and friend requests',
      importance: 4,
      visibility: 1,
      sound: 'default',
      vibration: true,
    })
  } catch {
    /* channel may already exist */
  }
}

async function installListeners(): Promise<void> {
  if (listenersInstalled) return
  listenersInstalled = true

  await PushNotifications.addListener('registration', (token) => {
    const value = (token?.value || '').trim()
    if (!value) {
      resolveTokenWaiters(null)
      return
    }
    lastRegistrationError = null
    const platform = platformForApi()
    writeStoredToken(value, platform)
    resolveTokenWaiters(value)
    if (!tokenStore.get()?.accessToken || !platform) return
    void registerNativePushDevice({
      platform,
      device_token: value,
      app_version: undefined,
    }).catch(() => {
      /* server may be fail-closed — resume sync retries */
    })
  })

  await PushNotifications.addListener('registrationError', (err) => {
    lastRegistrationError = String((err as { error?: string })?.error || 'registration_error')
    resolveTokenWaiters(null)
  })

  await PushNotifications.addListener('pushNotificationReceived', () => {
    /* foreground: OS / plugin presents per presentationOptions; no duplicate SPA toast */
  })

  await PushNotifications.addListener('pushNotificationActionPerformed', (action) => {
    const data = (action?.notification?.data || {}) as Record<string, unknown>
    openNotificationUrl(data.url ?? data.path)
  })
}

export function getLastNativePushRegistrationError(): string | null {
  return lastRegistrationError
}

async function deviceRegisteredOnBackend(
  platform: 'android' | 'ios',
  token: string,
): Promise<boolean> {
  try {
    const devices = await listNativePushDevices()
    return devices.some(
      (d) => d.platform === platform && (d.device_token || '').trim() === token,
    )
  } catch {
    return false
  }
}

/**
 * After login / bootstrap / resume: register when authenticated + platform enabled
 * + not opted out. If OS permission is already granted, do **not** require a second
 * in-app enable — obtain and register the FCM/APNs token automatically.
 * Waits for a token and confirms backend registration before returning granted.
 */
export async function syncNativePushAfterAuth(): Promise<NativePushSyncResult> {
  if (syncInFlight) return syncInFlight
  syncInFlight = syncNativePushAfterAuthInner().finally(() => {
    syncInFlight = null
  })
  return syncInFlight
}

async function syncNativePushAfterAuthInner(): Promise<NativePushSyncResult> {
  if (!isNativeShell()) return 'unsupported'
  const platform = platformForApi()
  if (!platform) return 'unsupported'
  if (!tokenStore.get()?.accessToken) return 'unauthenticated'
  // Explicit opt-out only — default is auto-register when OS permission is granted.
  if (!isNativePushDesired()) return 'skipped'

  let capability: NativePushCapability
  try {
    capability = await getNativePushCapability()
  } catch {
    return 'disabled'
  }
  const enabled = platform === 'android' ? capability.android_enabled : capability.ios_enabled
  if (!enabled) return 'disabled'

  await installListeners()
  await ensureAndroidChannels()

  let perm = await PushNotifications.checkPermissions()
  // Already granted in OS settings (e.g. Yaniv) — do not force another in-app prompt.
  if (perm.receive === 'prompt' || perm.receive === 'prompt-with-rationale') {
    perm = await PushNotifications.requestPermissions()
  }
  if (perm.receive !== 'granted') return 'denied'

  const pending = waitForDeviceToken()
  try {
    await PushNotifications.register()
  } catch {
    return 'registration_failed'
  }

  const token = (await pending) || readStoredToken()
  if (!token) return 'registration_failed'

  try {
    await registerNativePushDevice({ platform, device_token: token })
  } catch {
    return 'registration_failed'
  }

  // Confirm backend has this account+device — never report enabled from local cache alone.
  if (!(await deviceRegisteredOnBackend(platform, token))) {
    return 'registration_failed'
  }
  return 'granted'
}

/** Logout / account switch: unregister this device token from the current account only. */
export async function clearNativePushForLogout(): Promise<void> {
  if (!isNativeShell()) return
  const deviceToken = readStoredToken()
  // Snapshot auth before logoutLocal clears the store (logout may not await us).
  const access = tokenStore.get()?.accessToken
  if (deviceToken && access) {
    try {
      await fetch(`${getApiBaseUrl()}/push/native/devices`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${access}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ device_token: deviceToken }),
      })
    } catch {
      /* best-effort — other devices stay registered */
    }
  }
  try {
    await PushNotifications.removeAllListeners()
  } catch {
    /* ignore */
  }
  listenersInstalled = false
  resolveTokenWaiters(null)
  // Keep local FCM/APNs token string for re-register after next login.
}

export async function disableNativePush(): Promise<void> {
  setNativePushDesired(false)
  const token = readStoredToken()
  if (token && tokenStore.get()?.accessToken) {
    try {
      await deleteNativePushDevice(token)
    } catch {
      /* ignore */
    }
  }
  writeStoredToken(null, null)
}

export async function enableNativePush(): Promise<NativePushSyncResult> {
  setNativePushDesired(true)
  return syncNativePushAfterAuth()
}

export async function nativePushPermissionState(): Promise<
  'granted' | 'denied' | 'prompt' | 'unsupported'
> {
  if (!isNativeShell()) return 'unsupported'
  try {
    const perm = await PushNotifications.checkPermissions()
    if (perm.receive === 'granted') return 'granted'
    if (perm.receive === 'denied') return 'denied'
    return 'prompt'
  } catch {
    return 'unsupported'
  }
}

/**
 * True only when OS granted, user not opted out, and backend has this device
 * registered for the current authenticated account.
 */
export async function nativePushIsEnabled(): Promise<boolean> {
  if (!isNativeShell()) return false
  if (!isNativePushDesired()) return false
  if (!tokenStore.get()?.accessToken) return false
  try {
    const capability = await getNativePushCapability()
    const platform = platformForApi()
    if (!platform) return false
    const enabled = platform === 'android' ? capability.android_enabled : capability.ios_enabled
    if (!enabled) return false
    const perm = await PushNotifications.checkPermissions()
    if (perm.receive !== 'granted') return false
    const token = readStoredToken()
    if (!token) return false
    return deviceRegisteredOnBackend(platform, token)
  } catch {
    return false
  }
}

/** Test helper */
export function _resetNativePushListenersForTests(): void {
  listenersInstalled = false
  lastRegistrationError = null
  tokenWaiters = []
  regTimeoutMs = 20_000
  syncInFlight = null
}

/** Test helper */
export function _setNativePushRegTimeoutForTests(ms: number): void {
  regTimeoutMs = ms
}
