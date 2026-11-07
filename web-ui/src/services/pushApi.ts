import { apiRequest } from '@/services/api/client'

export type PushVapidPublicKey = {
  public_key: string
  enabled: boolean
}

export type PushSubscriptionRow = {
  id: string
  endpoint: string
  created_at: string
}

export async function getPushVapidPublicKey(): Promise<PushVapidPublicKey> {
  return apiRequest<PushVapidPublicKey>('/push/vapid-public-key', { auth: false })
}

export async function listPushSubscriptions(): Promise<PushSubscriptionRow[]> {
  return apiRequest<PushSubscriptionRow[]>('/push/subscriptions')
}

export async function savePushSubscription(input: {
  endpoint: string
  p256dh: string
  auth: string
  user_agent?: string
}): Promise<PushSubscriptionRow> {
  return apiRequest<PushSubscriptionRow>('/push/subscriptions', {
    method: 'POST',
    body: input,
  })
}

export async function deletePushSubscription(endpoint: string): Promise<void> {
  await apiRequest<void>('/push/subscriptions', {
    method: 'DELETE',
    body: { endpoint },
  })
}

export function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64)
  const out = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i)
  return out
}

const PUSH_DESIRED_KEY = 'fr.push.desired'

/** Push is on by default unless the user explicitly turned it off on this device. */
export function isPushDesired(): boolean {
  if (typeof window === 'undefined') return true
  try {
    const raw = localStorage.getItem(PUSH_DESIRED_KEY)
    if (raw === null) return true
    return raw !== '0' && raw !== 'false'
  } catch {
    return true
  }
}

export function setPushDesired(desired: boolean): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(PUSH_DESIRED_KEY, desired ? '1' : '0')
  } catch {
    /* private mode */
  }
}

export function pushSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  )
}

export async function enableRunwayPush(): Promise<'granted' | 'denied' | 'unsupported' | 'disabled'> {
  if (!pushSupported()) return 'unsupported'
  const vapid = await getPushVapidPublicKey()
  if (!vapid.enabled || !vapid.public_key) return 'disabled'

  const permission = await Notification.requestPermission()
  if (permission !== 'granted') return 'denied'

  const reg = await navigator.serviceWorker.ready
  const existing = await reg.pushManager.getSubscription()
  const sub =
    existing ??
    (await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapid.public_key) as BufferSource,
    }))

  const json = sub.toJSON()
  const endpoint = json.endpoint
  const p256dh = json.keys?.p256dh
  const auth = json.keys?.auth
  if (!endpoint || !p256dh || !auth) {
    throw new Error('Push subscription missing keys')
  }
  await savePushSubscription({
    endpoint,
    p256dh,
    auth,
    user_agent: navigator.userAgent,
  })
  setPushDesired(true)
  return 'granted'
}

export async function disableRunwayPush(): Promise<void> {
  setPushDesired(false)
  if (!pushSupported()) return
  const reg = await navigator.serviceWorker.ready
  const sub = await reg.pushManager.getSubscription()
  if (sub) {
    try {
      await deletePushSubscription(sub.endpoint)
    } catch {
      /* still drop local subscription */
    }
    await sub.unsubscribe()
  }
}

export async function runwayPushIsEnabled(): Promise<boolean> {
  if (!pushSupported()) return false
  if (Notification.permission !== 'granted') return false
  const reg = await navigator.serviceWorker.ready
  const sub = await reg.pushManager.getSubscription()
  if (!sub) return false
  try {
    const rows = await listPushSubscriptions()
    return rows.some((r) => r.endpoint === sub.endpoint)
  } catch {
    return false
  }
}

/**
 * Default-on path: subscribe when the user hasn't opted out.
 * Returns whether push is active after the attempt.
 */
export async function ensureDefaultRunwayPush(): Promise<{
  on: boolean
  result: 'granted' | 'denied' | 'unsupported' | 'disabled' | 'skipped' | 'already'
}> {
  if (!isPushDesired()) return { on: false, result: 'skipped' }
  if (!pushSupported()) return { on: false, result: 'unsupported' }
  if (await runwayPushIsEnabled()) return { on: true, result: 'already' }
  const result = await enableRunwayPush()
  return { on: result === 'granted', result }
}
