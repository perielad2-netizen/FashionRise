import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
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

/** While a like mutation is in flight, protect against every poll response. */
const LIKE_PENDING_BARRIER = Number.MAX_SAFE_INTEGER

type ProtectedLikeEntry = ProtectedCommentLike & {
  /**
   * Retain optimistic like against responses from requests with gen <= barrierGen.
   * Uses LIKE_PENDING_BARRIER until the mutation settles, then gen at settle time.
   */
  barrierGen: number
  seq: number
}

type PendingLocalEntry = {
  /** Retain local-only row against responses from requests with gen <= barrierGen. */
  barrierGen: number
}

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

/** Handle for an accepted like/unlike mutation (null when blocked by in-flight guard). */
export type CommentLikeMutationHandle = {
  seq: number
  /**
   * Revert optimistic state only if this mutation is still the latest for the comment.
   * Older failures must not overwrite a newer successful mutation.
   */
  revert: (prev: ProtectedCommentLike) => void
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
  ) => CommentLikeMutationHandle | null
  scrollToLatest: () => void
  clearNewCommentsIndicator: () => void
}

function bumpBackoff(current: number): number {
  return Math.min(
    LIVE_COMMENTS_BACKOFF_MAX_MS,
    Math.max(LIVE_COMMENTS_POLL_MS, current * 2),
  )
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

  const appActive = useAppIsActive({ enabled })
  const [comments, setComments] = useState<GalleryComment[] | null>(null)
  const [commentsError, setCommentsError] = useState<string | null>(null)
  const [commentsCount, setCommentsCount] = useState(0)
  const [newCommentsBelow, setNewCommentsBelow] = useState(0)

  const listRef = useRef<HTMLDivElement | null>(null)
  const commentsRef = useRef<GalleryComment[] | null>(null)
  const commentsCountRef = useRef(0)
  const inFlightRef = useRef(false)
  const genRef = useRef(0)
  const abortRef = useRef<AbortController | null>(null)
  const protectLikesRef = useRef(new Map<string, ProtectedLikeEntry>())
  const pendingLocalRef = useRef(new Map<string, PendingLocalEntry>())
  const likeSeqRef = useRef(new Map<string, number>())
  /** commentId → seq of the mutation currently in flight (API not settled). */
  const likeInFlightRef = useRef(new Map<string, number>())
  const backoffMsRef = useRef(LIVE_COMMENTS_POLL_MS)
  const wasActiveRef = useRef(appActive)
  const hasLoadedRef = useRef(false)
  const focusHandledRef = useRef(false)
  const scrollAfterRenderRef = useRef(false)
  /** Parent feed count synced at least once from an authoritative snapshot. */
  const countSyncedRef = useRef(false)
  const onCountChangeRef = useRef(onCountChange)
  const onFocusResolvedRef = useRef(onFocusCommentResolved)
  onCountChangeRef.current = onCountChange
  onFocusResolvedRef.current = onFocusCommentResolved

  const invalidateInFlight = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    inFlightRef.current = false
    genRef.current += 1
  }, [])

  const publishCount = useCallback((count: number, forceParentSync = false) => {
    const unchanged = commentsCountRef.current === count
    commentsCountRef.current = count
    setCommentsCount(count)
    // Authoritative snapshots must sync parent even when local count was already 0
    // (e.g. empty list after a nonzero feed comments_count).
    if (unchanged && countSyncedRef.current && !forceParentSync) return
    countSyncedRef.current = true
    onCountChangeRef.current?.(count)
  }, [])

  const applyRows = useCallback(
    (remote: GalleryComment[], mode: LoadMode, requestGen: number) => {
      const prev = commentsRef.current
      const nearBottom =
        mode === 'silent' && listRef.current
          ? isScrollNearBottom(listRef.current)
          : mode !== 'silent'
      const incoming = mode === 'silent' ? countNewCommentIds(prev, remote) : 0

      const protectForRequest = new Map<string, ProtectedCommentLike>()
      for (const [id, entry] of protectLikesRef.current) {
        if (entry.barrierGen >= requestGen) {
          protectForRequest.set(id, {
            liked_by_me: entry.liked_by_me,
            likes_count: entry.likes_count,
          })
        } else {
          protectLikesRef.current.delete(id)
        }
      }

      const retainLocalIds = new Set<string>()
      for (const [id, entry] of pendingLocalRef.current) {
        if (entry.barrierGen >= requestGen) {
          retainLocalIds.add(id)
        } else {
          pendingLocalRef.current.delete(id)
        }
      }

      const next = mergeGalleryComments(prev, remote, {
        protectLikes: protectForRequest,
        retainLocalIds,
      })

      const remoteIdSet = new Set(remote.map((r) => r.id).filter(Boolean))
      for (const [id, entry] of [...pendingLocalRef.current]) {
        if (remoteIdSet.has(id) || entry.barrierGen < requestGen) {
          pendingLocalRef.current.delete(id)
        }
      }

      commentsRef.current = next
      setComments(next)
      // Always push authoritative length to parent (incl. empty → 0).
      publishCount(next.length, true)
      setCommentsError(null)

      if (mode === 'silent' && incoming > 0) {
        if (nearBottom || prev == null) {
          scrollAfterRenderRef.current = true
          setNewCommentsBelow(0)
        } else {
          setNewCommentsBelow((n) => n + incoming)
        }
      }
    },
    [publishCount],
  )

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
        hasLoadedRef.current = true
        applyRows(rows, mode, gen)
        backoffMsRef.current = LIVE_COMMENTS_POLL_MS

        const want = (focusCommentId || '').trim()
        if (!focusHandledRef.current && want) {
          focusHandledRef.current = true
          const found = rows.some((r) => r.id === want)
          onFocusResolvedRef.current?.({ found, commentId: want })
        }
      } catch (err) {
        if (ac.signal.aborted || gen !== genRef.current) return
        backoffMsRef.current = bumpBackoff(backoffMsRef.current)
        if (mode === 'initial' && !hasLoadedRef.current) {
          setCommentsError(
            err instanceof ApiError ? err.message : 'Could not load comments.',
          )
          const want = (focusCommentId || '').trim()
          if (!focusHandledRef.current && want) {
            focusHandledRef.current = true
            onFocusResolvedRef.current?.({ found: false, commentId: want })
          }
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

  useLayoutEffect(() => {
    if (!scrollAfterRenderRef.current) return
    scrollAfterRenderRef.current = false
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [comments])

  // Reset list state when the look changes (not when the modal merely closes).
  useEffect(() => {
    focusHandledRef.current = false
    hasLoadedRef.current = false
    commentsRef.current = null
    commentsCountRef.current = 0
    setComments(null)
    setCommentsError(null)
    setCommentsCount(0)
    setNewCommentsBelow(0)
    protectLikesRef.current.clear()
    pendingLocalRef.current.clear()
    likeSeqRef.current.clear()
    likeInFlightRef.current.clear()
    countSyncedRef.current = false
    backoffMsRef.current = LIVE_COMMENTS_POLL_MS
    invalidateInFlight()
  }, [galleryItemId, invalidateInFlight])

  // Load / silent refresh when the modal opens; abort when closed.
  useEffect(() => {
    if (!enabled) {
      invalidateInFlight()
      setNewCommentsBelow(0)
      return
    }
    focusHandledRef.current = false
    void fetchComments(hasLoadedRef.current ? 'silent' : 'initial')
  }, [enabled, fetchComments, galleryItemId, invalidateInFlight])

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

  // Abort when backgrounded; refresh immediately on foreground return.
  useEffect(() => {
    const was = wasActiveRef.current
    wasActiveRef.current = appActive
    if (!enabled) return
    if (!appActive) {
      invalidateInFlight()
      return
    }
    if (!was && appActive) {
      backoffMsRef.current = LIVE_COMMENTS_POLL_MS
      void fetchComments('silent')
    }
  }, [appActive, enabled, fetchComments, invalidateInFlight])

  // Abort in-flight work if the session ends while open.
  useEffect(() => {
    if (!enabled) return
    const id = window.setInterval(() => {
      if (!tokenStore.get()?.accessToken) {
        invalidateInFlight()
      }
    }, 1000)
    return () => window.clearInterval(id)
  }, [enabled, invalidateInFlight])

  useEffect(() => {
    return () => {
      invalidateInFlight()
    }
  }, [invalidateInFlight])

  const upsertLocalComment = useCallback(
    (row: GalleryComment) => {
      if (!row?.id) return
      pendingLocalRef.current.set(row.id, { barrierGen: genRef.current })
      const byId = new Map<string, GalleryComment>()
      for (const r of commentsRef.current ?? []) {
        if (r?.id) byId.set(r.id, r)
      }
      byId.set(row.id, row)
      const merged = mergeGalleryComments(null, [...byId.values()])
      commentsRef.current = merged
      setComments(merged)
      publishCount(merged.length)
      setCommentsError(null)
      hasLoadedRef.current = true
      scrollAfterRenderRef.current = true
      setNewCommentsBelow(0)
    },
    [publishCount],
  )

  const applyLikeFields = useCallback((commentId: string, fields: ProtectedCommentLike) => {
    const prev = commentsRef.current
    const merged = (prev ?? []).map((row) =>
      row.id === commentId
        ? { ...row, liked_by_me: fields.liked_by_me, likes_count: fields.likes_count }
        : row,
    )
    commentsRef.current = merged
    setComments(merged)
  }, [])

  const patchCommentLike = useCallback(
    (
      commentId: string,
      next: ProtectedCommentLike,
      settle: Promise<unknown>,
    ): CommentLikeMutationHandle | null => {
      // Per-comment guard: overlapping like/unlike on the same row is rejected.
      if (likeInFlightRef.current.has(commentId)) return null

      const seq = (likeSeqRef.current.get(commentId) ?? 0) + 1
      likeSeqRef.current.set(commentId, seq)
      likeInFlightRef.current.set(commentId, seq)
      protectLikesRef.current.set(commentId, {
        ...next,
        barrierGen: LIKE_PENDING_BARRIER,
        seq,
      })
      applyLikeFields(commentId, next)

      const releaseInFlight = () => {
        if (likeInFlightRef.current.get(commentId) === seq) {
          likeInFlightRef.current.delete(commentId)
        }
      }

      const handle: CommentLikeMutationHandle = {
        seq,
        revert: (prevState) => {
          // Stale failure must not undo a newer successful mutation.
          if (likeSeqRef.current.get(commentId) !== seq) return
          releaseInFlight()
          protectLikesRef.current.set(commentId, {
            ...prevState,
            barrierGen: genRef.current,
            seq,
          })
          applyLikeFields(commentId, prevState)
        },
      }

      void Promise.resolve(settle).then(
        () => {
          if (likeSeqRef.current.get(commentId) !== seq) return
          const cur = protectLikesRef.current.get(commentId)
          if (!cur || cur.seq !== seq) return
          releaseInFlight()
          // Polls that already started before settle must not clobber this result.
          protectLikesRef.current.set(commentId, {
            ...cur,
            barrierGen: genRef.current,
          })
        },
        () => {
          // Rejection without revert — release lock so the caller can retry.
          if (likeSeqRef.current.get(commentId) !== seq) return
          releaseInFlight()
          const cur = protectLikesRef.current.get(commentId)
          if (cur?.seq === seq) {
            protectLikesRef.current.set(commentId, {
              ...cur,
              barrierGen: genRef.current,
            })
          }
        },
      )

      return handle
    },
    [applyLikeFields],
  )

  const scrollToLatest = useCallback(() => {
    scrollAfterRenderRef.current = true
    setNewCommentsBelow(0)
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
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
