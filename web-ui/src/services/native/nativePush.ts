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
 *
 * Auto (bootstrap / Settings mount) and manual (Settings toggle) share
 * `syncNativePushAfterAuth` / `enableNativePush` — do not fork paths.
 */
import { App } from '@capacitor/app'
import { PushNotifications } from '@capacitor/push-notifications'
import { ApiError, apiRequest, getApiBaseUrl } from '@/services/api/client'
import { tokenStore } from '@/services/auth/tokenStore'
import { handleNotificationDestination } from './notificationNavigation'
import { isNativeShell, nativePlatform } from './platform'

/** Marketing version + build for native_push_devices.app_version diagnostics (≤64). */
async function readNativeAppVersionLabel(): Promise<string | undefined> {
  if (!isNativeShell()) return undefined
  try {
    const info = await App.getInfo()
    const version = (info?.version || '').trim()
    const build = (info?.build || '').trim()
    const label = [version, build ? `(${build})` : ''].filter(Boolean).join(' ').trim()
    return label.slice(0, 64) || undefined
  } catch {
    return undefined
  }
}

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

/** Discrete stages for QA — never include full FCM/APNs tokens. */
export type NativePushFailStage =
  | 'capability'
  | 'permission'
  | 'register_call'
  | 'token_error'
  | 'token_timeout'
  | 'backend_post'
  | 'backend_confirm'

export type NativePushDiagnostic = {
  stage: NativePushFailStage | 'ok'
  code: string
  message: string
  at: number
  /** First/last 4 chars only when a token was involved — never the full value. */
  tokenFingerprint?: string
}

const TOKEN_KEY = 'fr.nativePush.token'
const PLATFORM_KEY = 'fr.nativePush.platform'
const DESIRED_KEY = 'fr.nativePush.desired'
let regTimeoutMs = 20_000

let listenersInstalled = false
let lastRegistrationError: string | null = null
let lastDiagnostic: NativePushDiagnostic | null = null
let tokenWaiters: Array<(token: string | null) => void> = []
let syncInFlight: Promise<NativePushSyncResult> | null = null

function platformForApi(): 'android' | 'ios' | null {
  const p = nativePlatform()
  if (p === 'android' || p === 'ios') return p
  return null
}

function tokenFingerprint(token: string | null | undefined): string | undefined {
  const t = (token || '').trim()
  if (t.length < 12) return undefined
  return `${t.slice(0, 4)}…${t.slice(-4)}(len=${t.length})`
}

function sanitizePushError(raw: unknown): string {
  let text = String(raw ?? '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!text) return 'unknown_error'
  // Strip anything that looks like a long token / credential blob.
  text = text.replace(/[A-Za-z0-9_-]{40,}/g, '[redacted]')
  if (text.length > 180) text = `${text.slice(0, 177)}…`
  return text
}

function setDiagnostic(
  stage: NativePushFailStage | 'ok',
  code: string,
  message: string,
  token?: string | null,
): void {
  lastDiagnostic = {
    stage,
    code,
    message: sanitizePushError(message),
    at: Date.now(),
    tokenFingerprint: tokenFingerprint(token),
  }
  try {
    // Safe diagnostic only — never log full tokens or auth credentials.
    console.info('[nativePush]', {
      stage: lastDiagnostic.stage,
      code: lastDiagnostic.code,
      message: lastDiagnostic.message,
      tokenFingerprint: lastDiagnostic.tokenFingerprint ?? null,
    })
  } catch {
    /* ignore */
  }
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
  destination_contract_version?: number
}): Promise<NativePushDeviceRow> {
  return apiRequest<NativePushDeviceRow>('/push/native/devices', {
    method: 'POST',
    body: {
      ...input,
      destination_contract_version: input.destination_contract_version ?? 2,
    },
  })
}

export async function deleteNativePushDevice(deviceToken: string): Promise<void> {
  await apiRequest<void>('/push/native/devices', {
    method: 'DELETE',
    body: { device_token: deviceToken },
  })
}

function openNotificationUrl(rawUrl: unknown): void {
  // Centralized path for all notification types (likes, comments, operator tests).
  // Queues until auth/router ready; rejects unsafe destinations.
  handleNotificationDestination(rawUrl)
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

/**
 * Install tap/receive listeners as early as possible (cold start).
 * Safe before auth — destinations queue until navigation is marked ready.
 * Registration listeners still require a later syncNativePushAfterAuth.
 */
export async function installNativePushInteractionListeners(): Promise<void> {
  if (!isNativeShell()) return
  if (listenersInstalled) return
  listenersInstalled = true

  await PushNotifications.addListener('registration', (token) => {
    const value = (token?.value || '').trim()
    if (!value) {
      lastRegistrationError = 'empty_token'
      setDiagnostic('token_error', 'empty_token', 'FCM/APNs returned an empty token')
      resolveTokenWaiters(null)
      return
    }
    lastRegistrationError = null
    const platform = platformForApi()
    writeStoredToken(value, platform)
    resolveTokenWaiters(value)
    if (!tokenStore.get()?.accessToken || !platform) return
    void (async () => {
      try {
        const app_version = await readNativeAppVersionLabel()
        await registerNativePushDevice({
          platform,
          device_token: value,
          app_version,
          destination_contract_version: 2,
        })
      } catch {
        /* server may be fail-closed — resume sync retries */
      }
    })()
  })

  await PushNotifications.addListener('registrationError', (err) => {
    const raw = sanitizePushError((err as { error?: string })?.error || 'registration_error')
    lastRegistrationError = raw
    setDiagnostic('token_error', 'registration_error', raw)
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

async function installListeners(): Promise<void> {
  await installNativePushInteractionListeners()
}

export function getLastNativePushRegistrationError(): string | null {
  return lastRegistrationError
}

export function getLastNativePushDiagnostic(): NativePushDiagnostic | null {
  return lastDiagnostic
}

/**
 * User-facing copy for Settings / Runway. Maps the failing stage to an
 * actionable hint without exposing tokens or credentials.
 */
export function formatNativePushRegistrationFailureMessage(): string {
  const d = lastDiagnostic
  if (!d || d.stage === 'ok') {
    return 'Could not register this device for push. Check Google Play Services and try again.'
  }
  switch (d.stage) {
    case 'capability':
      return 'Native push is not enabled on the server for this platform yet.'
    case 'permission':
      return 'Notifications are blocked for FashionRise. Enable them in system settings, then try again.'
    case 'register_call':
      return 'Push plugin failed to start. Update the app from Play Store / Internal testing and retry.'
    case 'token_error': {
      const hint = d.message.toLowerCase()
      if (hint.includes('play') || hint.includes('service_not_available') || hint.includes('gms')) {
        return `Could not get an FCM token (${d.message}). Update Google Play Services, confirm you’re online, then retry.`
      }
      if (hint.includes('firebase') || hint.includes('not initialized')) {
        return `Firebase did not initialize on this build (${d.message}). Reinstall the latest Internal testing build.`
      }
      return `Could not get an FCM token (${d.message}). Check Google Play Services and network, then retry.`
    }
    case 'token_timeout':
      return 'FCM token timed out. Update Google Play Services, stay online for ~30s, then retry from Settings.'
    case 'backend_post': {
      const statusMatch = /^post_failed_(\d+|unknown)$/i.exec(d.code || '')
      const status =
        statusMatch && statusMatch[1] !== 'unknown' ? Number(statusMatch[1]) : NaN
      const msg = (d.message || '').toLowerCase()
      if (status === 401 || msg.includes('session expired')) {
        return 'Got a device token but registration needs a valid session. Sign in again and retry.'
      }
      if (status === 403 || msg.includes('forbidden')) {
        return 'Got a device token but the API gateway blocked device registration (HTTP 403). Retry after the server allowlist is updated — signing in again will not help.'
      }
      if (status === 0 || msg.includes('failed to fetch') || msg.includes('network')) {
        return 'Got a device token but could not reach the registration API. Check network and retry.'
      }
      return 'Got a device token but the server rejected registration. Retry from Settings; sign in again only if you see a session error.'
    }
    case 'backend_confirm':
      return 'Server did not confirm this device yet. Wait a moment and retry from Settings.'
    default:
      return 'Could not register this device for push. Check Google Play Services and try again.'
  }
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

async function requestNativeToken(forceRefresh: boolean): Promise<string | null> {
  if (!forceRefresh) {
    const existing = readStoredToken()
    if (existing) return existing
  }
  lastRegistrationError = null
  const pending = waitForDeviceToken()
  try {
    await PushNotifications.register()
  } catch (err) {
    setDiagnostic('register_call', 'register_threw', sanitizePushError(err))
    resolveTokenWaiters(null)
    return null
  }
  const token = (await pending) || readStoredToken()
  if (token) return token
  if (lastRegistrationError) {
    setDiagnostic('token_error', 'registration_error', lastRegistrationError)
  } else {
    setDiagnostic(
      'token_timeout',
      'token_timeout',
      'No FCM/APNs token within timeout — Play Services or Firebase install may be unavailable',
    )
  }
  return null
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
  } catch (err) {
    setDiagnostic('capability', 'capability_fetch_failed', sanitizePushError(err))
    return 'disabled'
  }
  const enabled = platform === 'android' ? capability.android_enabled : capability.ios_enabled
  if (!enabled) {
    setDiagnostic('capability', 'platform_disabled', `${platform}_disabled`)
    return 'disabled'
  }

  await installListeners()
  await ensureAndroidChannels()

  let perm = await PushNotifications.checkPermissions()
  // Already granted in OS settings (e.g. Yaniv) — do not force another in-app prompt.
  if (perm.receive === 'prompt' || perm.receive === 'prompt-with-rationale') {
    perm = await PushNotifications.requestPermissions()
  }
  if (perm.receive !== 'granted') {
    setDiagnostic('permission', 'os_denied', `receive=${perm.receive}`)
    return 'denied'
  }

  // Prefer a fresh FCM token when none is cached; one retry helps cold Play Services.
  let token = await requestNativeToken(false)
  if (!token) {
    token = await requestNativeToken(true)
  }
  if (!token) return 'registration_failed'

  try {
    const app_version = await readNativeAppVersionLabel()
    await registerNativePushDevice({
      platform,
      device_token: token,
      app_version,
      destination_contract_version: 2,
    })
  } catch (err) {
    const status = err instanceof ApiError ? err.status : 0
    const detail =
      err instanceof ApiError
        ? `HTTP ${status}: ${sanitizePushError(err.message || err)}`
        : sanitizePushError(err)
    setDiagnostic('backend_post', `post_failed_${status || 'unknown'}`, detail, token)
    return 'registration_failed'
  }

  // Confirm backend has this account+device — never report enabled from local cache alone.
  if (!(await deviceRegisteredOnBackend(platform, token))) {
    setDiagnostic(
      'backend_confirm',
      'confirm_missing',
      'Device list did not include this token after register',
      token,
    )
    return 'registration_failed'
  }
  setDiagnostic('ok', 'registered', 'backend confirmed device', token)
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
  // Re-install tap listeners so a notification tap during/after logout still queues.
  void installNativePushInteractionListeners().catch(() => {
    /* ignore */
  })
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
  lastDiagnostic = null
  tokenWaiters = []
  regTimeoutMs = 20_000
  syncInFlight = null
}

/** Test helper */
export function _setNativePushRegTimeoutForTests(ms: number): void {
  regTimeoutMs = ms
}
