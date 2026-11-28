import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { GalleryComment } from '@/services/galleryApi'

const listGalleryComments = vi.fn()

vi.mock('@/services/galleryApi', () => ({
  listGalleryComments: (...args: unknown[]) => listGalleryComments(...args),
}))

vi.mock('@/services/auth/tokenStore', () => ({
  tokenStore: {
    get: () => ({ accessToken: 'access', refreshToken: 'refresh' }),
  },
}))

vi.mock('@capacitor/app', () => ({
  App: {
    addListener: vi.fn(async () => ({ remove: vi.fn() })),
  },
}))

vi.mock('@/services/native/platform', () => ({
  isNativeShell: () => false,
  nativePlatform: () => 'web',
}))

import { useLiveGalleryComments } from '@/lib/useLiveGalleryComments'
import { LIVE_COMMENTS_POLL_MS } from '@/lib/liveGalleryComments'

function row(id: string, body: string, created_at: string): GalleryComment {
  return {
    id,
    gallery_item_id: 'g1',
    user_id: 'u1',
    body,
    moderation_status: 'ok',
    likes_count: 0,
    created_at,
    username: 'alice',
    liked_by_me: false,
  }
}

describe('useLiveGalleryComments', () => {
  beforeEach(() => {
    listGalleryComments.mockReset()
    vi.useFakeTimers({ shouldAdvanceTime: true })
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      get: () => 'visible',
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('loads on open and polls for incoming comments without duplicates', async () => {
    listGalleryComments
      .mockResolvedValueOnce([row('c1', 'first', '2026-11-28T00:00:00Z')])
      .mockResolvedValueOnce([
        row('c1', 'first', '2026-11-28T00:00:00Z'),
        row('c2', 'second', '2026-11-28T00:01:00Z'),
      ])
      .mockResolvedValue([
        row('c1', 'first', '2026-11-28T00:00:00Z'),
        row('c2', 'second', '2026-11-28T00:01:00Z'),
      ])

    const { result, unmount } = renderHook(() =>
      useLiveGalleryComments({ galleryItemId: 'g1', enabled: true }),
    )

    await waitFor(() => expect(result.current.comments?.map((c) => c.id)).toEqual(['c1']))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(LIVE_COMMENTS_POLL_MS + 50)
    })

    await waitFor(() =>
      expect(result.current.comments?.map((c) => c.id)).toEqual(['c1', 'c2']),
    )
    expect(result.current.commentsCount).toBe(2)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(LIVE_COMMENTS_POLL_MS + 50)
    })
    await waitFor(() => expect(listGalleryComments.mock.calls.length).toBeGreaterThanOrEqual(3))
    expect(result.current.comments?.map((c) => c.id)).toEqual(['c1', 'c2'])

    unmount()
  })

  it('removes moderated/deleted comments from authoritative polls', async () => {
    listGalleryComments
      .mockResolvedValueOnce([
        row('c1', 'keep', '2026-11-28T00:00:00Z'),
        row('c2', 'gone-soon', '2026-11-28T00:01:00Z'),
      ])
      .mockResolvedValue([row('c1', 'keep', '2026-11-28T00:00:00Z')])

    const { result } = renderHook(() =>
      useLiveGalleryComments({ galleryItemId: 'g1', enabled: true }),
    )
    await waitFor(() => expect(result.current.comments?.map((c) => c.id)).toEqual(['c1', 'c2']))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(LIVE_COMMENTS_POLL_MS + 50)
    })
    await waitFor(() => expect(result.current.comments?.map((c) => c.id)).toEqual(['c1']))
    expect(result.current.commentsCount).toBe(1)
  })

  it('keeps own post against a poll that started before the post completed', async () => {
    let resolvePoll!: (rows: GalleryComment[]) => void
    const slowPoll = new Promise<GalleryComment[]>((r) => {
      resolvePoll = r
    })
    listGalleryComments.mockImplementationOnce(() => slowPoll)

    const { result } = renderHook(() =>
      useLiveGalleryComments({ galleryItemId: 'g1', enabled: true }),
    )

    await waitFor(() => expect(listGalleryComments).toHaveBeenCalledTimes(1))

    act(() => {
      result.current.upsertLocalComment(row('mine', 'hello', '2026-11-28T00:02:00Z'))
    })
    expect(result.current.comments?.map((c) => c.id)).toEqual(['mine'])

    await act(async () => {
      resolvePoll([row('older', 'pre-existing', '2026-11-28T00:00:00Z')])
    })

    await waitFor(() =>
      expect(result.current.comments?.map((c) => c.id)).toEqual(['older', 'mine']),
    )
  })

  it('upserts own comment immediately without waiting for poll', async () => {
    listGalleryComments.mockResolvedValue([])
    const { result } = renderHook(() =>
      useLiveGalleryComments({ galleryItemId: 'g1', enabled: true }),
    )
    await waitFor(() => expect(result.current.comments).toEqual([]))

    act(() => {
      result.current.upsertLocalComment(row('mine', 'hello', '2026-11-28T00:02:00Z'))
    })
    expect(result.current.comments?.map((c) => c.id)).toEqual(['mine'])
    expect(result.current.commentsCount).toBe(1)

    listGalleryComments.mockResolvedValueOnce([
      row('mine', 'hello', '2026-11-28T00:02:00Z'),
      row('theirs', 'hi', '2026-11-28T00:03:00Z'),
    ])
    await act(async () => {
      await vi.advanceTimersByTimeAsync(LIVE_COMMENTS_POLL_MS + 50)
    })
    await waitFor(() =>
      expect(result.current.comments?.map((c) => c.id)).toEqual(['mine', 'theirs']),
    )
  })

  it('protects likes against polls that arrive before the mutation settled', async () => {
    listGalleryComments.mockResolvedValue([row('c1', 'first', '2026-11-28T00:00:00Z')])
    const { result } = renderHook(() =>
      useLiveGalleryComments({ galleryItemId: 'g1', enabled: true }),
    )
    await waitFor(() => expect(result.current.comments?.[0]?.id).toBe('c1'))

    let resolveLike!: () => void
    const settle = new Promise<void>((r) => {
      resolveLike = r
    })
    act(() => {
      result.current.patchCommentLike('c1', { liked_by_me: true, likes_count: 1 }, settle)
    })
    expect(result.current.comments?.[0]?.liked_by_me).toBe(true)

    // Poll may start after optimistic like but before settle — still protected.
    listGalleryComments.mockResolvedValueOnce([
      { ...row('c1', 'first', '2026-11-28T00:00:00Z'), liked_by_me: false, likes_count: 0 },
    ])
    await act(async () => {
      await vi.advanceTimersByTimeAsync(LIVE_COMMENTS_POLL_MS + 50)
    })
    await waitFor(() => expect(listGalleryComments.mock.calls.length).toBeGreaterThanOrEqual(2))
    expect(result.current.comments?.[0]?.liked_by_me).toBe(true)
    expect(result.current.comments?.[0]?.likes_count).toBe(1)

    await act(async () => {
      resolveLike()
    })
    // Still liked after settle; later authoritative polls may sync remote.
    expect(result.current.comments?.[0]?.liked_by_me).toBe(true)
  })

  it('protects likes against an in-flight poll that resolves after settle', async () => {
    let resolvePoll!: (rows: GalleryComment[]) => void
    const slowPoll = new Promise<GalleryComment[]>((r) => {
      resolvePoll = r
    })
    listGalleryComments
      .mockResolvedValueOnce([row('c1', 'first', '2026-11-28T00:00:00Z')])
      .mockImplementationOnce(() => slowPoll)

    const { result } = renderHook(() =>
      useLiveGalleryComments({ galleryItemId: 'g1', enabled: true }),
    )
    await waitFor(() => expect(result.current.comments?.[0]?.id).toBe('c1'))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(LIVE_COMMENTS_POLL_MS + 50)
    })
    await waitFor(() => expect(listGalleryComments.mock.calls.length).toBeGreaterThanOrEqual(2))

    act(() => {
      result.current.patchCommentLike('c1', { liked_by_me: true, likes_count: 1 }, Promise.resolve())
    })
    expect(result.current.comments?.[0]?.liked_by_me).toBe(true)

    await act(async () => {
      await Promise.resolve()
    })

    await act(async () => {
      resolvePoll([
        { ...row('c1', 'first', '2026-11-28T00:00:00Z'), liked_by_me: false, likes_count: 0 },
      ])
    })

    await waitFor(() => expect(result.current.comments?.[0]?.liked_by_me).toBe(true))
    expect(result.current.comments?.[0]?.likes_count).toBe(1)
  })

  it('handles failed like mutation without unhandled rejection', async () => {
    listGalleryComments.mockResolvedValue([row('c1', 'first', '2026-11-28T00:00:00Z')])
    const { result } = renderHook(() =>
      useLiveGalleryComments({ galleryItemId: 'g1', enabled: true }),
    )
    await waitFor(() => expect(result.current.comments?.[0]?.id).toBe('c1'))

    const rejected = Promise.reject(new Error('like failed'))
    // Prevent Vitest from treating this as an unhandled rejection before the hook attaches.
    rejected.catch(() => undefined)

    let handle: ReturnType<typeof result.current.patchCommentLike> = null
    act(() => {
      handle = result.current.patchCommentLike(
        'c1',
        { liked_by_me: true, likes_count: 1 },
        rejected,
      )
    })
    expect(handle).not.toBeNull()
    expect(result.current.comments?.[0]?.liked_by_me).toBe(true)

    await act(async () => {
      await Promise.resolve()
    })

    act(() => {
      handle?.revert({ liked_by_me: false, likes_count: 0 })
    })
    expect(result.current.comments?.[0]?.liked_by_me).toBe(false)
    expect(result.current.comments?.[0]?.likes_count).toBe(0)
  })

  it('blocks overlapping like/unlike mutations on the same comment', async () => {
    listGalleryComments.mockResolvedValue([row('c1', 'first', '2026-11-28T00:00:00Z')])
    const { result } = renderHook(() =>
      useLiveGalleryComments({ galleryItemId: 'g1', enabled: true }),
    )
    await waitFor(() => expect(result.current.comments?.[0]?.id).toBe('c1'))

    let resolveFirst!: () => void
    const firstSettle = new Promise<void>((r) => {
      resolveFirst = r
    })

    let first: ReturnType<typeof result.current.patchCommentLike> = null
    let second: ReturnType<typeof result.current.patchCommentLike> = null
    act(() => {
      first = result.current.patchCommentLike(
        'c1',
        { liked_by_me: true, likes_count: 1 },
        firstSettle,
      )
      second = result.current.patchCommentLike(
        'c1',
        { liked_by_me: false, likes_count: 0 },
        Promise.resolve(),
      )
    })
    expect(first).not.toBeNull()
    expect(second).toBeNull()
    expect(result.current.comments?.[0]?.liked_by_me).toBe(true)
    expect(result.current.comments?.[0]?.likes_count).toBe(1)

    await act(async () => {
      resolveFirst()
      await Promise.resolve()
    })

    let after: ReturnType<typeof result.current.patchCommentLike> = null
    act(() => {
      after = result.current.patchCommentLike(
        'c1',
        { liked_by_me: false, likes_count: 0 },
        Promise.resolve(),
      )
    })
    expect(after).not.toBeNull()
    expect(result.current.comments?.[0]?.liked_by_me).toBe(false)
  })

  it('ignores stale revert after a newer successful mutation', async () => {
    listGalleryComments.mockResolvedValue([row('c1', 'first', '2026-11-28T00:00:00Z')])
    const { result } = renderHook(() =>
      useLiveGalleryComments({ galleryItemId: 'g1', enabled: true }),
    )
    await waitFor(() => expect(result.current.comments?.[0]?.id).toBe('c1'))

    let resolveFirst!: () => void
    const firstSettle = new Promise<void>((r) => {
      resolveFirst = r
    })

    let first: ReturnType<typeof result.current.patchCommentLike> = null
    act(() => {
      first = result.current.patchCommentLike(
        'c1',
        { liked_by_me: true, likes_count: 1 },
        firstSettle,
      )
    })
    expect(first).not.toBeNull()

    await act(async () => {
      resolveFirst()
      await Promise.resolve()
    })

    let second: ReturnType<typeof result.current.patchCommentLike> = null
    act(() => {
      second = result.current.patchCommentLike(
        'c1',
        { liked_by_me: false, likes_count: 0 },
        Promise.resolve(),
      )
    })
    expect(second).not.toBeNull()
    expect(result.current.comments?.[0]?.liked_by_me).toBe(false)

    // Late failure revert from the older mutation must not clobber the newer unlike.
    act(() => {
      first?.revert({ liked_by_me: false, likes_count: 0 })
    })
    expect(result.current.comments?.[0]?.liked_by_me).toBe(false)
    expect(result.current.comments?.[0]?.likes_count).toBe(0)

    act(() => {
      first?.revert({ liked_by_me: true, likes_count: 1 })
    })
    expect(result.current.comments?.[0]?.liked_by_me).toBe(false)
    expect(result.current.comments?.[0]?.likes_count).toBe(0)
  })

  it('syncs parent count to 0 when the first snapshot is empty', async () => {
    listGalleryComments.mockResolvedValue([])
    const onCountChange = vi.fn()
    const { result } = renderHook(() =>
      useLiveGalleryComments({
        galleryItemId: 'g1',
        enabled: true,
        onCountChange,
      }),
    )
    await waitFor(() => expect(result.current.comments).toEqual([]))
    expect(result.current.commentsCount).toBe(0)
    expect(onCountChange).toHaveBeenCalledWith(0)
  })

  it('clears initial load error after a successful refresh', async () => {
    listGalleryComments.mockRejectedValueOnce(new Error('network'))
    const { result } = renderHook(() =>
      useLiveGalleryComments({ galleryItemId: 'g1', enabled: true }),
    )
    await waitFor(() => expect(result.current.commentsError).toBeTruthy())

    listGalleryComments.mockResolvedValue([row('c1', 'ok', '2026-11-28T00:00:00Z')])
    await act(async () => {
      await result.current.refreshComments()
    })
    await waitFor(() => {
      expect(result.current.commentsError).toBeNull()
      expect(result.current.comments?.map((c) => c.id)).toEqual(['c1'])
    })
  })

  it('stops polling when disabled (modal closed) and aborts work', async () => {
    listGalleryComments.mockResolvedValue([])
    const { result, rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) =>
        useLiveGalleryComments({ galleryItemId: 'g1', enabled }),
      { initialProps: { enabled: true } },
    )
    await waitFor(() => expect(listGalleryComments).toHaveBeenCalledTimes(1))

    rerender({ enabled: false })
    const calls = listGalleryComments.mock.calls.length
    await act(async () => {
      await vi.advanceTimersByTimeAsync(LIVE_COMMENTS_POLL_MS * 3)
    })
    expect(listGalleryComments.mock.calls.length).toBe(calls)
    expect(result.current.newCommentsBelow).toBe(0)
  })

  it('refreshes immediately when returning to foreground', async () => {
    listGalleryComments.mockResolvedValue([row('c1', 'first', '2026-11-28T00:00:00Z')])
    const { result } = renderHook(() =>
      useLiveGalleryComments({ galleryItemId: 'g1', enabled: true }),
    )
    await waitFor(() => expect(result.current.comments?.[0]?.id).toBe('c1'))

    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      get: () => 'hidden',
    })
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'))
    })

    listGalleryComments.mockResolvedValueOnce([
      row('c1', 'first', '2026-11-28T00:00:00Z'),
      row('c2', 'back', '2026-11-28T00:05:00Z'),
    ])
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      get: () => 'visible',
    })
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'))
    })

    await waitFor(() =>
      expect(result.current.comments?.map((c) => c.id)).toEqual(['c1', 'c2']),
    )
  })

  it('ignores stale responses when a newer request started', async () => {
    let resolveFirst!: (rows: GalleryComment[]) => void
    const first = new Promise<GalleryComment[]>((r) => {
      resolveFirst = r
    })
    listGalleryComments.mockImplementationOnce(() => first)
    listGalleryComments.mockResolvedValueOnce([row('fresh', 'new', '2026-11-28T00:09:00Z')])

    const { result, rerender } = renderHook(
      ({ id }: { id: string }) => useLiveGalleryComments({ galleryItemId: id, enabled: true }),
      { initialProps: { id: 'g1' } },
    )

    rerender({ id: 'g2' })
    await waitFor(() => expect(listGalleryComments.mock.calls.length).toBeGreaterThanOrEqual(2))

    await act(async () => {
      resolveFirst([row('stale', 'old', '2026-11-28T00:00:00Z')])
    })

    await waitFor(() => expect(result.current.comments?.map((c) => c.id)).toEqual(['fresh']))
    expect(result.current.comments?.some((c) => c.id === 'stale')).toBe(false)
  })
})
