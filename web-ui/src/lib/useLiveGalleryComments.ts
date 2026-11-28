import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '@/services/api/client'
import {
  listGalleryComments,
  type GalleryComment,
} from '@/services/galleryApi'
import { tokenStore } from '@/services/auth/tokenStore'
import {
  LIVE_COMMENTS_BACKOFF_MAX_MS,
  LIVE_COMMENTS_POLL_MS,
  countNewCommentIds,
  isScrollNearBottom,
  mergeGalleryComments,
  type ProtectedCommentLike,
} from '@/lib/liveGalleryComments'
import { useAppIsActive } from '@/lib/useAppIsActive'

type LoadMode = 'initial' | 'silent'

export type UseLiveGalleryCommentsOptions = {
  galleryItemId: string
  /** Comments UI is open (modal / lightbox). */
  enabled: boolean
  /** When set, resolve highlight after the first successful load for this open cycle. */
  focusCommentId?: string | null
  onCountChange?: (count: number) => void
  onFocusCommentResolved?: (result: {
    found: boolean
    commentId: string | null
  }) => void
}

export type UseLiveGalleryCommentsResult = {
  comments: GalleryComment[] | null
  commentsError: string | null
  commentsCount: number
  newCommentsBelow: number
  listRef: React.RefObject<HTMLDivElement | null>
  refreshComments: () => Promise<void>
  upsertLocalComment: (row: GalleryComment) => void
  patchCommentLike: (
    commentId: string,
    next: ProtectedCommentLike,
    settle: Promise<unknown>,
  ) => void
  scrollToLatest: () => void
  clearNewCommentsIndicator: () => void
}

/**
 * Shared gallery comment list + 3s live poll for Web / PWA / native shells.
 * Does not own draft text or input focus.
 */
export function useLiveGalleryComments(
  options: UseLiveGalleryCommentsOptions,
): UseLiveGalleryCommentsResult {
  const {
    galleryItemId,
    enabled,
    focusCommentId = null,
    onCountChange,
    onFocusCommentResolved,
  } = options

  const appActive = useAppIsActive()
  const [comments, setComments] = useState<GalleryComment[] | null>(null)
  const [commentsError, setCommentsError] = useState<string | null>(null)
  const [commentsCount, setCommentsCount] = useState(0)
  const [newCommentsBelow, setNewCommentsBelow] = useState(0)

  const listRef = useRef<HTMLDivElement | null>(null)
  const inFlightRef = useRef(false)
  const genRef = useRef(0)
  const abortRef = useRef<AbortController | null>(null)
  const protectLikesRef = useRef(new Map<string, ProtectedCommentLike>())
  const backoffMsRef = useRef(LIVE_COMMENTS_POLL_MS)
  const wasActiveRef = useRef(appActive)
  const hasLoadedRef = useRef(false)
  const focusHandledRef = useRef(false)
  const onCountChangeRef = useRef(onCountChange)
  const onFocusResolvedRef = useRef(onFocusCommentResolved)
  onCountChangeRef.current = onCountChange
  onFocusResolvedRef.current = onFocusCommentResolved

  const applyRows = useCallback((remote: GalleryComment[], mode: LoadMode) => {
    setComments((prev) => {
      const nearBottom =
        mode === 'silent' && listRef.current
          ? isScrollNearBottom(listRef.current)
          : mode !== 'silent'
      const incoming = mode === 'silent' ? countNewCommentIds(prev, remote) : 0
      const next = mergeGalleryComments(prev, remote, protectLikesRef.current)
      setCommentsCount(next.length)
      onCountChangeRef.current?.(next.length)

      if (mode === 'silent' && incoming > 0) {
        if (nearBottom || prev == null) {
          queueMicrotask(() => {
            const el = listRef.current
            if (!el) return
            el.scrollTop = el.scrollHeight
          })
          setNewCommentsBelow(0)
        } else {
          setNewCommentsBelow((n) => n + incoming)
        }
      }
      return next
    })
  }, [])

  const fetchComments = useCallback(
    async (mode: LoadMode) => {
      if (!galleryItemId) return
      if (!tokenStore.get()?.accessToken) return
      if (inFlightRef.current) return

      inFlightRef.current = true
      const gen = ++genRef.current
      abortRef.current?.abort()
      const ac = new AbortController()
      abortRef.current = ac

      try {
        const rows = await listGalleryComments(galleryItemId, ac.signal)
        if (gen !== genRef.current) return
        if (mode === 'initial') setCommentsError(null)
        hasLoadedRef.current = true
        applyRows(rows, mode)
        backoffMsRef.current = LIVE_COMMENTS_POLL_MS

        const want = (focusCommentId || '').trim()
        if (!focusHandledRef.current && want) {
          focusHandledRef.current = true
          const found = rows.some((r) => r.id === want)
          onFocusResolvedRef.current?.({ found, commentId: want })
        }
      } catch (err) {
        if (ac.signal.aborted || gen !== genRef.current) return
        if (mode === 'initial') {
          setCommentsError(
            err instanceof ApiError ? err.message : 'Could not load comments.',
          )
          const want = (focusCommentId || '').trim()
          if (!focusHandledRef.current && want) {
            focusHandledRef.current = true
            onFocusResolvedRef.current?.({ found: false, commentId: want })
          }
        } else {
          backoffMsRef.current = Math.min(
            LIVE_COMMENTS_BACKOFF_MAX_MS,
            Math.max(LIVE_COMMENTS_POLL_MS, backoffMsRef.current * 2),
          )
        }
      } finally {
        if (gen === genRef.current) inFlightRef.current = false
      }
    },
    [applyRows, focusCommentId, galleryItemId],
  )

  const refreshComments = useCallback(async () => {
    await fetchComments(hasLoadedRef.current ? 'silent' : 'initial')
  }, [fetchComments])

  // Reset list state when the look changes (not when the modal merely closes).
  useEffect(() => {
    focusHandledRef.current = false
    hasLoadedRef.current = false
    setComments(null)
    setCommentsError(null)
    setCommentsCount(0)
    setNewCommentsBelow(0)
    protectLikesRef.current.clear()
    backoffMsRef.current = LIVE_COMMENTS_POLL_MS
    abortRef.current?.abort()
    inFlightRef.current = false
  }, [galleryItemId])

  // Load / silent refresh when the modal opens.
  useEffect(() => {
    if (!enabled) {
      abortRef.current?.abort()
      inFlightRef.current = false
      setNewCommentsBelow(0)
      return
    }
    focusHandledRef.current = false
    void fetchComments(hasLoadedRef.current ? 'silent' : 'initial')
  }, [enabled, fetchComments, galleryItemId])

  // Poll while open + foreground + authenticated.
  useEffect(() => {
    if (!enabled || !appActive) return
    if (!tokenStore.get()?.accessToken) return

    let cancelled = false
    let timer: number | undefined

    const schedule = () => {
      timer = window.setTimeout(() => {
        if (cancelled) return
        void fetchComments('silent').finally(() => {
          if (!cancelled) schedule()
        })
      }, backoffMsRef.current)
    }
    schedule()

    return () => {
      cancelled = true
      if (timer != null) window.clearTimeout(timer)
    }
  }, [appActive, enabled, fetchComments, galleryItemId])

  // Immediate refresh when returning to foreground with modal open.
  useEffect(() => {
    const was = wasActiveRef.current
    wasActiveRef.current = appActive
    if (!enabled) return
    if (!was && appActive) {
      backoffMsRef.current = LIVE_COMMENTS_POLL_MS
      void fetchComments('silent')
    }
  }, [appActive, enabled, fetchComments])

  // Abort in-flight work if the session ends while open.
  useEffect(() => {
    if (!enabled) return
    const id = window.setInterval(() => {
      if (!tokenStore.get()?.accessToken) {
        abortRef.current?.abort()
        inFlightRef.current = false
      }
    }, 1000)
    return () => window.clearInterval(id)
  }, [enabled])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const upsertLocalComment = useCallback((row: GalleryComment) => {
    setComments((prev) => {
      const next = mergeGalleryComments(prev, [row], protectLikesRef.current)
      setCommentsCount(next.length)
      onCountChangeRef.current?.(next.length)
      return next
    })
    hasLoadedRef.current = true
    queueMicrotask(() => {
      const el = listRef.current
      if (el) el.scrollTop = el.scrollHeight
    })
    setNewCommentsBelow(0)
  }, [])

  const patchCommentLike = useCallback(
    (commentId: string, next: ProtectedCommentLike, settle: Promise<unknown>) => {
      protectLikesRef.current.set(commentId, next)
      setComments((prev) =>
        (prev ?? []).map((row) =>
          row.id === commentId
            ? { ...row, liked_by_me: next.liked_by_me, likes_count: next.likes_count }
            : row,
        ),
      )
      void settle.finally(() => {
        protectLikesRef.current.delete(commentId)
      })
    },
    [],
  )

  const scrollToLatest = useCallback(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
    setNewCommentsBelow(0)
  }, [])

  const clearNewCommentsIndicator = useCallback(() => setNewCommentsBelow(0), [])

  return {
    comments,
    commentsError,
    commentsCount,
    newCommentsBelow,
    listRef,
    refreshComments,
    upsertLocalComment,
    patchCommentLike,
    scrollToLatest,
    clearNewCommentsIndicator,
  }
}
