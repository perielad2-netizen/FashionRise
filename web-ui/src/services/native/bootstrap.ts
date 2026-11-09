import { App } from '@capacitor/app'
import { StatusBar, Style } from '@capacitor/status-bar'
import { SplashScreen } from '@capacitor/splash-screen'
import { isNativeShell } from './platform'

/** Soften native chrome once the SPA mounts. Safe no-op on web. */
export async function bootstrapNativeShell(): Promise<void> {
  if (!isNativeShell()) return
  try {
    await StatusBar.setStyle({ style: Style.Dark })
    await StatusBar.setBackgroundColor({ color: '#090F1F' })
    // Keep fixed portals (Runway sheets) below the status bar on iOS.
    await StatusBar.setOverlaysWebView({ overlay: false })
  } catch {
    /* web / unsupported */
  }
  try {
    await SplashScreen.hide()
  } catch {
    /* ignore */
  }
  void App.addListener('backButton', ({ canGoBack }) => {
    if (canGoBack) window.history.back()
    else void App.exitApp()
  })
}
