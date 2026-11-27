import { useCallback, useEffect, useState } from 'react'
import {
  disableRunwayPush,
  enableRunwayPush,
  ensureDefaultRunwayPush,
  runwayPushIsEnabled,
} from '@/services/pushApi'
import { isNativeShell } from '@/services/native/platform'
import { nativePushPermissionState } from '@/services/native/nativePush'
import { openAppNotificationSettings } from '@/services/native/openAppNotificationSettings'
import styles from './GlobalHeader.module.css'

/**
 * Shared Notifications toggle for Settings (and reusable by Runway).
 * Preference / visibility — not a mandatory second activation.
 * If OS permission is already granted and the user has not opted out,
 * auto-register FCM/APNs and confirm backend registration.
 */
export function NotificationsSettingsToggle() {
  const [on, setOn] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [osDenied, setOsDenied] = useState(false)
  const native = isNativeShell()

  const refresh = useCallback(async () => {
    try {
      const enabled = await runwayPushIsEnabled()
      setOn(enabled)
      if (native) {
        const perm = await nativePushPermissionState()
        setOsDenied(perm === 'denied')
      } else {
        setOsDenied(
          typeof Notification !== 'undefined' && Notification.permission === 'denied',
        )
      }
    } catch {
      setOn(false)
    }
  }, [native])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      // Auto-activate when OS already granted (e.g. system settings) — no second prompt.
      if (native) {
        try {
          await ensureDefaultRunwayPush()
        } catch {
          /* ignore — refresh still reports backend-confirmed state */
        }
      }
      if (!cancelled) await refresh()
    })()
    return () => {
      cancelled = true
    }
  }, [native, refresh])

  const onToggle = useCallback(async () => {
    if (busy) return
    setBusy(true)
    setNotice(null)
    try {
      if (on) {
        await disableRunwayPush()
        setOn(false)
        setNotice(native ? 'Notifications off for this device' : 'Browser notifications off')
        return
      }
      if (osDenied) {
        const opened = await openAppNotificationSettings()
        setNotice(
          opened
            ? native
              ? 'Enable notifications for FashionRise in system settings, then return here.'
              : 'Enable notifications for this site in browser settings, then return here.'
            : native
              ? 'Open Android Settings → Apps → FashionRise → Notifications, then return here.'
              : 'Enable notifications in your browser settings, then return here.',
        )
        return
      }
      const result = await enableRunwayPush()
      if (result === 'granted') {
        setOn(true)
        setOsDenied(false)
        setNotice(
          native
            ? 'Notifications on — FashionRise will alert you on this device'
            : 'Notifications on — we’ll alert you in this browser',
        )
        return
      }
      if (result === 'denied') {
        setOsDenied(true)
        setOn(false)
        setNotice(
          native
            ? 'Notifications blocked in system settings'
            : 'Notifications blocked in browser settings',
        )
        return
      }
      if (result === 'registration_failed') {
        setOn(false)
        setNotice(
          'Could not register this device for push. Check Google Play Services and try again.',
        )
        return
      }
      if (result === 'disabled') {
        setOn(false)
        setNotice(
          native
            ? 'Native push isn’t enabled on the server yet'
            : 'Push isn’t configured on the server yet',
        )
        return
      }
      setOn(false)
      setNotice('Notifications aren’t supported here')
    } catch {
      setNotice('Could not update notifications')
    } finally {
      setBusy(false)
      void refresh()
    }
  }, [busy, native, on, osDenied, refresh])

  return (
    <div className={styles.notifBlock} data-testid="settings-notifications">
      <div className={styles.notifRow}>
        <div>
          <p className={styles.notifTitle}>Notifications</p>
          <p className={styles.notifHint}>
            {native
              ? 'Likes, comments, and friend alerts on this device'
              : 'Likes, comments, and friend alerts in this browser'}
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={on}
          aria-busy={busy}
          disabled={busy}
          className={on ? styles.notifSwitchOn : styles.notifSwitchOff}
          data-testid="settings-notifications-toggle"
          onClick={() => void onToggle()}
        >
          {on ? 'On' : 'Off'}
        </button>
      </div>
      {osDenied ? (
        <button
          type="button"
          className={styles.notifSettingsLink}
          data-testid="settings-notifications-open-os"
          onClick={() => void openAppNotificationSettings()}
        >
          Open system notification settings
        </button>
      ) : null}
      {notice ? (
        <p className={styles.notifNotice} role="status">
          {notice}
        </p>
      ) : null}
    </div>
  )
}
