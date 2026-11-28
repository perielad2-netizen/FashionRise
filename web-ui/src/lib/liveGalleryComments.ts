import type { GalleryComment } from '@/services/galleryApi'

/** Local like mutation that must not be clobbered by a stale poll. */
export type ProtectedCommentLike = {
  liked_by_me: boolean
  likes_count: number
}

export type MergeGalleryCommentsOptions = {
  protectLikes?: ReadonlyMap<string, ProtectedCommentLike>
  /**
   * Local-only ids to keep when missing from an authoritative remote snapshot
   * (e.g. own post still absent from a poll that started before the post).
   */
  retainLocalIds?: ReadonlySet<string>
}

export function sortCommentsChronologically(rows: GalleryComment[]): GalleryComment[] {
  return [...rows].sort((a, b) => {
    const byTime = (a.created_at || '').localeCompare(b.created_at || '')
    if (byTime !== 0) return byTime
    return a.id.localeCompare(b.id)
  })
}

/**
 * Apply an authoritative remote comment list.
 * Remote is the source of truth (deleted/moderated rows disappear).
 * Optional local-only ids may be retained; protected likes win over remote fields.
 */
export function mergeGalleryComments(
  local: GalleryComment[] | null | undefined,
  remote: GalleryComment[],
  options?: MergeGalleryCommentsOptions | ReadonlyMap<string, ProtectedCommentLike>,
): GalleryComment[] {
  // Narrow Map vs options bag — ReadonlyMap is not eliminated by `instanceof Map` alone.
  const opts: MergeGalleryCommentsOptions =
    options == null
      ? {}
      : options instanceof Map
        ? { protectLikes: options }
        : (options as MergeGalleryCommentsOptions)
  const protectLikes = opts.protectLikes
  const retainLocalIds = opts.retainLocalIds

  const remoteIds = new Set<string>()
  const map = new Map<string, GalleryComment>()
  for (const row of remote) {
    if (!row?.id) continue
    remoteIds.add(row.id)
    const protectedLike = protectLikes?.get(row.id)
    if (protectedLike) {
      map.set(row.id, {
        ...row,
        liked_by_me: protectedLike.liked_by_me,
        likes_count: protectedLike.likes_count,
      })
    } else {
      map.set(row.id, row)
    }
  }

  for (const row of local ?? []) {
    if (!row?.id || remoteIds.has(row.id)) continue
    if (retainLocalIds?.has(row.id)) {
      map.set(row.id, row)
    }
  }

  return sortCommentsChronologically([...map.values()])
}

export function commentIds(rows: GalleryComment[] | null | undefined): Set<string> {
  const out = new Set<string>()
  for (const row of rows ?? []) {
    if (row?.id) out.add(row.id)
  }
  return out
}

/** Count remote ids not present in previous snapshot (incoming comments). */
export function countNewCommentIds(
  previous: GalleryComment[] | null | undefined,
  next: GalleryComment[],
): number {
  const seen = commentIds(previous)
  let n = 0
  for (const row of next) {
    if (row?.id && !seen.has(row.id)) n += 1
  }
  return n
}

export function isScrollNearBottom(el: HTMLElement, thresholdPx = 80): boolean {
  const remaining = el.scrollHeight - el.scrollTop - el.clientHeight
  return remaining <= thresholdPx
}

export const LIVE_COMMENTS_POLL_MS = 3000
export const LIVE_COMMENTS_BACKOFF_MAX_MS = 30_000
