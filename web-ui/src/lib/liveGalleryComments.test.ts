import { describe, expect, it } from 'vitest'
import type { GalleryComment } from '@/services/galleryApi'
import {
  countNewCommentIds,
  isScrollNearBottom,
  mergeGalleryComments,
  sortCommentsChronologically,
} from '@/lib/liveGalleryComments'

function c(
  partial: Partial<GalleryComment> & Pick<GalleryComment, 'id' | 'created_at'>,
): GalleryComment {
  return {
    gallery_item_id: 'g1',
    user_id: 'u1',
    body: 'x',
    moderation_status: 'ok',
    likes_count: 0,
    liked_by_me: false,
    username: 'a',
    ...partial,
  }
}

describe('liveGalleryComments helpers', () => {
  it('dedupes by id and sorts chronologically', () => {
    const local = [c({ id: 'b', created_at: '2026-11-28T00:02:00Z', body: 'old-b' })]
    const remote = [
      c({ id: 'a', created_at: '2026-11-28T00:01:00Z', body: 'a' }),
      c({ id: 'b', created_at: '2026-11-28T00:02:00Z', body: 'new-b', likes_count: 3 }),
      c({ id: 'c', created_at: '2026-11-28T00:03:00Z', body: 'c' }),
    ]
    const merged = mergeGalleryComments(local, remote)
    expect(merged.map((r) => r.id)).toEqual(['a', 'b', 'c'])
    expect(merged[1]?.body).toBe('new-b')
    expect(merged[1]?.likes_count).toBe(3)
  })

  it('preserves protected likes over remote poll values', () => {
    const local = [c({ id: 'a', created_at: '2026-11-28T00:01:00Z', liked_by_me: true, likes_count: 2 })]
    const remote = [c({ id: 'a', created_at: '2026-11-28T00:01:00Z', liked_by_me: false, likes_count: 1 })]
    const protect = new Map([['a', { liked_by_me: true, likes_count: 2 }]])
    const merged = mergeGalleryComments(local, remote, protect)
    expect(merged[0]?.liked_by_me).toBe(true)
    expect(merged[0]?.likes_count).toBe(2)
  })

  it('counts only newly arrived comment ids', () => {
    const prev = [c({ id: 'a', created_at: '2026-11-28T00:01:00Z' })]
    const next = [
      c({ id: 'a', created_at: '2026-11-28T00:01:00Z' }),
      c({ id: 'b', created_at: '2026-11-28T00:02:00Z' }),
    ]
    expect(countNewCommentIds(prev, next)).toBe(1)
    expect(countNewCommentIds(null, next)).toBe(2)
  })

  it('sorts stable by created_at then id', () => {
    const rows = [
      c({ id: 'z', created_at: '2026-11-28T00:01:00Z' }),
      c({ id: 'a', created_at: '2026-11-28T00:01:00Z' }),
      c({ id: 'm', created_at: '2026-11-28T00:00:00Z' }),
    ]
    expect(sortCommentsChronologically(rows).map((r) => r.id)).toEqual(['m', 'a', 'z'])
  })

  it('detects near-bottom scroll', () => {
    const el = {
      scrollHeight: 500,
      scrollTop: 400,
      clientHeight: 80,
    } as HTMLElement
    expect(isScrollNearBottom(el, 80)).toBe(true)
    el.scrollTop = 100
    expect(isScrollNearBottom(el, 80)).toBe(false)
  })
})
