import { useEffect, useState } from 'react'
import { fetchJobImageBlob } from '@/services/ai/magicApi'

/** Lazy authenticated object URL for an AI job image. Revokes on change/unmount. */
export function useAuthJobImage(jobId: string | null | undefined, enabled = true): {
  url: string | null
  error: string | null
  loading: boolean
} {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!enabled || !jobId) {
      setUrl(null)
      setError(null)
      setLoading(false)
      return
    }
    let cancelled = false
    let objectUrl: string | null = null
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    void fetchJobImageBlob(jobId, controller.signal)
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (cancelled || controller.signal.aborted) return
        setUrl(null)
        setLoading(false)
        setError(err instanceof Error ? err.message : 'Could not load image')
      })
    return () => {
      cancelled = true
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [jobId, enabled])

  return { url, error, loading }
}
