import { ApiError, apiRequest } from '@/services/api/client'

export type LookSide = {
  job_id: string
  studio_side: 'front' | 'back' | null
  has_image: boolean
  summary: string | null
  created_at: string
}

export type LookRecord = {
  id: string
  title: string
  is_favorite: boolean
  is_archived: boolean
  kind: 'single' | 'dual'
  created_at: string
  updated_at: string
  front: LookSide | null
  back: LookSide | null
  design_id: string | null
  magic_operation_id: string | null
}

export type LookListResponse = {
  items: LookRecord[]
  total: number
  limit: number
  offset: number
}

export type LookFilter = 'all' | 'favorites' | 'archived'

export type LookUpdate = {
  title?: string
  is_favorite?: boolean
  is_archived?: boolean
}

export async function listLooks(
  opts: {
    filter?: LookFilter
    q?: string
    limit?: number
    offset?: number
    signal?: AbortSignal
  } = {},
): Promise<LookListResponse> {
  const params = new URLSearchParams()
  params.set('filter', opts.filter ?? 'all')
  if (opts.q?.trim()) params.set('q', opts.q.trim())
  params.set('limit', String(opts.limit ?? 24))
  params.set('offset', String(opts.offset ?? 0))
  return apiRequest<LookListResponse>(`/looks?${params.toString()}`, {
    method: 'GET',
    signal: opts.signal,
  })
}

export async function getLook(lookId: string, signal?: AbortSignal): Promise<LookRecord> {
  return apiRequest<LookRecord>(`/looks/${lookId}`, { method: 'GET', signal })
}

export async function updateLook(lookId: string, patch: LookUpdate): Promise<LookRecord> {
  return apiRequest<LookRecord>(`/looks/${lookId}`, {
    method: 'PATCH',
    body: patch,
  })
}

export type DeleteLookResult =
  | { ok: true; alreadyGone: boolean }
  | { ok: false; error: string; outcomeUncertain: boolean; canRetry: boolean }

const DELETE_OFFLINE_MESSAGE =
  'You are offline. The look was not deleted. Reconnect and try again.'

const DELETE_STILL_PRESENT_MESSAGE =
  'FashionRise could not delete this look, and it is still in My Looks. Try again.'

const DELETE_UNCONFIRMED_MESSAGE =
  'Could not confirm whether the look was deleted. Refresh My Looks before trying again.'

function isOffline(): boolean {
  return typeof navigator !== 'undefined' && navigator.onLine === false
}

type LookPresence = 'present' | 'absent' | 'unknown'

async function ownerLookPresence(lookId: string): Promise<LookPresence> {
  try {
    // Search across common filters so archived looks still count as present.
    for (const filter of ['all', 'archived', 'favorites'] as const) {
      const page = await listLooks({ filter, limit: 100, offset: 0 })
      if (page.items.some((item) => item.id === lookId)) return 'present'
    }
    return 'absent'
  } catch {
    try {
      await getLook(lookId)
      return 'present'
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return 'absent'
      return 'unknown'
    }
  }
}

function deleteResultFromPresence(
  presence: LookPresence,
  opts: { alreadyGone: boolean; presentError: string },
): DeleteLookResult {
  if (presence === 'absent') return { ok: true, alreadyGone: opts.alreadyGone }
  if (presence === 'present') {
    return {
      ok: false,
      error: opts.presentError,
      outcomeUncertain: false,
      canRetry: true,
    }
  }
  return {
    ok: false,
    error: DELETE_UNCONFIRMED_MESSAGE,
    outcomeUncertain: true,
    canRetry: true,
  }
}

/**
 * Permanently remove a look from My Looks (server tombstone).
 * Success is claimed only on DELETE 204 or confirmed absence after 404/uncertain responses.
 */
export async function deleteLook(lookId: string): Promise<DeleteLookResult> {
  if (isOffline()) {
    return { ok: false, error: DELETE_OFFLINE_MESSAGE, outcomeUncertain: false, canRetry: true }
  }

  try {
    await apiRequest<void>(`/looks/${lookId}`, { method: 'DELETE' })
    return { ok: true, alreadyGone: false }
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return deleteResultFromPresence(await ownerLookPresence(lookId), {
        alreadyGone: true,
        presentError: DELETE_STILL_PRESENT_MESSAGE,
      })
    }

    const uncertain =
      err instanceof ApiError && (err.status === 0 || err.status >= 500 || err.status === 408)
    if (uncertain || !(err instanceof ApiError)) {
      return deleteResultFromPresence(await ownerLookPresence(lookId), {
        alreadyGone: true,
        presentError:
          err instanceof ApiError && err.status !== 0
            ? err.message
            : 'Could not reach FashionRise. The look was not deleted. Try again.',
      })
    }

    return {
      ok: false,
      error: err.status !== 0 ? err.message : 'Could not delete this look. Try again.',
      outcomeUncertain: false,
      canRetry: err.status === 0 || err.status >= 500,
    }
  }
}

/** Primary image job for gallery thumbnails (front preferred). */
export function lookThumbnailJobId(look: LookRecord): string | null {
  if (look.front?.has_image) return look.front.job_id
  if (look.back?.has_image) return look.back.job_id
  return null
}
