/**
 * Open OS notification settings for this app (Android plugin / iOS app-settings).
 */
import { Capacitor, registerPlugin } from '@capacitor/core'
import { isNativeShell, nativePlatform } from './platform'

type NotificationSettingsPlugin = {
  open(): Promise<void>
}

const FashionRiseNotificationSettings = registerPlugin<NotificationSettingsPlugin>(
  'FashionRiseNotificationSettings',
)

/** Returns true when the settings screen was opened (or a best-effort attempt was made). */
export async function openAppNotificationSettings(): Promise<boolean> {
  if (!isNativeShell()) return false
  const platform = nativePlatform()
  try {
    if (platform === 'android') {
      await FashionRiseNotificationSettings.open()
      return true
    }
    if (platform === 'ios') {
      // iOS has no public deep-link into notification toggles; open app settings.
      window.location.href = 'app-settings:'
      return true
    }
  } catch {
    /* fall through */
  }
  // Last resort: Android application details via package URI when plugin missing.
  if (platform === 'android' && Capacitor.isNativePlatform()) {
    try {
      window.open('package:app.fashionrise.studio', '_system')
      return true
    } catch {
      return false
    }
  }
  return false
}
