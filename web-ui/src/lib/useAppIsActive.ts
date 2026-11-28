import { useEffect, useState } from 'react'
import { App } from '@capacitor/app'
import { isNativeShell } from '@/services/native/platform'

function readDocumentVisible(): boolean {
  if (typeof document === 'undefined') return true
  return document.visibilityState !== 'hidden'
}

/**
 * True while the app/tab is in the foreground.
 * Web: `visibilitychange`. Native: Capacitor `appStateChange` + visibility.
 */
export function useAppIsActive(): boolean {
  const [active, setActive] = useState(readDocumentVisible)

  useEffect(() => {
    const onVis = () => setActive(readDocumentVisible())
    document.addEventListener('visibilitychange', onVis)

    let removeNative: (() => void) | undefined
    if (isNativeShell()) {
      void App.addListener('appStateChange', ({ isActive }) => {
        setActive(Boolean(isActive) && readDocumentVisible())
      }).then((handle) => {
        removeNative = () => {
          void handle.remove()
        }
      })
    }

    return () => {
      document.removeEventListener('visibilitychange', onVis)
      removeNative?.()
    }
  }, [])

  return active
}
