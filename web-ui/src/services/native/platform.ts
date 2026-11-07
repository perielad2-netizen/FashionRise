import { Capacitor } from '@capacitor/core'

export function isNativeShell(): boolean {
  try {
    return Capacitor.isNativePlatform()
  } catch {
    return false
  }
}

export function nativePlatform(): 'ios' | 'android' | 'web' {
  try {
    const p = Capacitor.getPlatform()
    if (p === 'ios' || p === 'android') return p
    return 'web'
  } catch {
    return 'web'
  }
}

/** True when this build was compiled for the store shell (may still run in browser during debug). */
export function isNativeBuild(): boolean {
  return String(import.meta.env.VITE_NATIVE_SHELL || '') === 'true'
}
