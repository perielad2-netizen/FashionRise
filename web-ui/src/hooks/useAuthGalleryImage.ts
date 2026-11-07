import { useEffect, useState } from 'react'
import { fetchGalleryImageBlob } from '@/services/galleryApi'

/** Lazy authenticated object URL for a published Runway gallery image. */
export function useAuthGalleryImage(galleryItemId: string | null | undefined, enabled = true): {
  url: string | null
  error: string | null
  loading: boolean
} {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!enabled || !galleryItemId) {
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
    void fetchGalleryImageBlob(galleryItemId, controller.signal)
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
  }, [galleryItemId, enabled])

  return { url, error, loading }
}
