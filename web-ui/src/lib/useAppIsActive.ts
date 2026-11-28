import { useEffect, useState } from 'react'
import { App } from '@capacitor/app'
import { isNativeShell } from '@/services/native/platform'

function readDocumentVisible(): boolean {
  if (typeof document === 'undefined') return true
  return document.visibilityState !== 'hidden'
}

export type UseAppIsActiveOptions = {
  /** When false, listeners are not installed and the last known value is frozen. */
  enabled?: boolean
}

/**
 * True while the app/tab is in the foreground.
 * Web: `visibilitychange`. Native: Capacitor `appStateChange` + visibility.
 *
 * Pass `enabled: false` to tear down listeners (e.g. comments modal closed).
 */
export function useAppIsActive(options: UseAppIsActiveOptions = {}): boolean {
  const enabled = options.enabled !== false
  const [active, setActive] = useState(readDocumentVisible)

  useEffect(() => {
    if (!enabled) return

    setActive(readDocumentVisible())
    const onVis = () => setActive(readDocumentVisible())
    document.addEventListener('visibilitychange', onVis)

    let cancelled = false
    let removeNative: (() => void) | undefined
    if (isNativeShell()) {
      void App.addListener('appStateChange', ({ isActive }) => {
        if (cancelled) return
        setActive(Boolean(isActive) && readDocumentVisible())
      }).then((handle) => {
        if (cancelled) {
          void handle.remove()
          return
        }
        removeNative = () => {
          void handle.remove()
        }
      })
    }

    return () => {
      cancelled = true
      document.removeEventListener('visibilitychange', onVis)
      removeNative?.()
    }
  }, [enabled])

  return active
}
