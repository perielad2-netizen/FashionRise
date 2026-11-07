import type { CapacitorConfig } from '@capacitor/cli'

/**
 * FashionRise native shell (App Store + Play Store).
 * Web UI is the product; Capacitor wraps the production `dist/` build.
 *
 * API calls use absolute https://fashionrise.app/api/v1 (see .env.native).
 * Apple/Google IAP credits the same Stars wallet — no custom card UI.
 */
const config: CapacitorConfig = {
  appId: 'app.fashionrise.studio',
  appName: 'FashionRise',
  webDir: 'dist',
  server: {
    // Local assets only — do not point at a remote URL for store builds.
    androidScheme: 'https',
    iosScheme: 'capacitor',
    allowNavigation: ['fashionrise.app', '*.fashionrise.app'],
  },
  plugins: {
    SplashScreen: {
      launchAutoHide: true,
      backgroundColor: '#090F1F',
      showSpinner: false,
    },
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#090F1F',
    },
    PushNotifications: {
      presentationOptions: ['badge', 'sound', 'alert'],
    },
  },
  android: {
    allowMixedContent: false,
    backgroundColor: '#090F1F',
  },
  ios: {
    contentInset: 'automatic',
    backgroundColor: '#090F1F',
    preferredContentMode: 'mobile',
  },
}

export default config
