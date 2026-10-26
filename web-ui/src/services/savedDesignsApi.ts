import { ApiError, apiRequest } from '@/services/api/client'
import { getDesign, listMyDesigns, type DesignRead } from '@/services/designsApi'
import {
  buildSavedDesignPayload,
  parseSavedDesign,
  partitionSavedDesigns,
  snapshotFingerprint,
  type SavedDesignLibrary,
  type SavedDesignRecord,
  type SavedDesignSnapshot,
} from '@/lib/savedDesign'

export type SaveDesignRequest = {
  ownerId: string
  title: string
  snapshot: SavedDesignSnapshot
  saveRequestId: string
  sourceRevision: number | null
  /**
   * True when an earlier attempt with this saveRequestId may have reached the server
   * (lost response, timeout, 5xx). The owner's list is checked before any new POST.
   */
  previousAttemptUncertain: boolean
}

export type SaveDesignResult =
  | { ok: true; record: SavedDesignRecord; recovered: boolean }
  | { ok: false; error: string; outcomeUncertain: boolean }

const OFFLINE_MESSAGE =
  'You are offline. The design was not saved. Reconnect and try again — your sketch is still in Studio.'

function isOffline(): boolean {
  return typeof navigator !== 'undefined' && navigator.onLine === false
}

/** Network failures and 5xx responses may hide a committed create. 4xx means it was rejected. */
function outcomeUncertain(err: unknown): boolean {
  if (!(err instanceof ApiError)) return true
  return err.status === 0 || err.status >= 500
}

async function findBySaveRequestId(
  ownerId: string,
  saveRequestId: string,
): Promise<SavedDesignRecord | null> {
  const mine = await listMyDesigns()
  for (const row of mine) {
    const parsed = parseSavedDesign(row, ownerId)
    if (parsed && parsed.saveRequestId === saveRequestId) return parsed
  }
  return null
}

function acknowledged(
  row: DesignRead,
  req: SaveDesignRequest,
): SavedDesignRecord | null {
  const parsed = parseSavedDesign(row, req.ownerId)
  if (!parsed || parsed.saveRequestId !== req.saveRequestId) return null
  if (snapshotFingerprint(parsed.snapshot) !== snapshotFingerprint(req.snapshot)) return null
  return parsed
}

/**
 * Create one immutable, owner-private saved design. Idempotent per `saveRequestId`:
 * a retry after an uncertain outcome first looks the request id up in the owner's
 * list and returns the existing row instead of creating a duplicate.
 * Success is reported only for a server-acknowledged row whose snapshot matches.
 */
export async function saveDesignSnapshot(req: SaveDesignRequest): Promise<SaveDesignResult> {
  if (isOffline()) return { ok: false, error: OFFLINE_MESSAGE, outcomeUncertain: req.previousAttemptUncertain }

  if (req.previousAttemptUncertain) {
    try {
      const existing = await findBySaveRequestId(req.ownerId, req.saveRequestId)
      if (existing) {
        if (snapshotFingerprint(existing.snapshot) !== snapshotFingerprint(req.snapshot)) {
          return {
            ok: false,
            error: 'A different design was saved with this request. Close the dialog and save again.',
            outcomeUncertain: false,
          }
        }
        return { ok: true, record: existing, recovered: true }
      }
    } catch (err) {
      // Cannot prove the earlier attempt failed — never POST blindly.
      return {
        ok: false,
        error:
          err instanceof ApiError && err.status !== 0
            ? err.message
            : 'Could not reach FashionRise to confirm the save. Try again when you are back online.',
        outcomeUncertain: true,
      }
    }
  }

  const payload = buildSavedDesignPayload({
    title: req.title,
    snapshot: req.snapshot,
    saveRequestId: req.saveRequestId,
    sourceRevision: req.sourceRevision,
  })

  let created: DesignRead
  try {
    created = await apiRequest<DesignRead>('/designs', { method: 'POST', body: payload })
  } catch (err) {
    const uncertain = outcomeUncertain(err)
    if (uncertain) {
      try {
        const existing = await findBySaveRequestId(req.ownerId, req.saveRequestId)
        if (existing && snapshotFingerprint(existing.snapshot) === snapshotFingerprint(req.snapshot)) {
          return { ok: true, record: existing, recovered: true }
        }
      } catch {
        /* fall through: outcome still unknown */
      }
    }
    return {
      ok: false,
      error:
        err instanceof ApiError && err.status !== 0
          ? err.message
          : 'Could not reach FashionRise. The design was not confirmed as saved. Try again.',
      outcomeUncertain: uncertain,
    }
  }

  const record = acknowledged(created, req)
  if (!record) {
    return {
      ok: false,
      error: 'The server response did not match your sketch. The design was not confirmed as saved.',
      outcomeUncertain: true,
    }
  }
  return { ok: true, record, recovered: false }
}

export async function listSavedDesigns(
  ownerId: string,
  signal?: AbortSignal,
): Promise<SavedDesignLibrary> {
  const mine = await listMyDesigns(signal)
  return partitionSavedDesigns(mine, ownerId)
}

export type FetchSavedDesignResult =
  | { ok: true; record: SavedDesignRecord }
  | { ok: false; error: string; reason: 'not-found' | 'invalid' | 'network' }

/** Fresh owner-authorized read used before reopening. */
export async function fetchSavedDesign(
  ownerId: string,
  designId: string,
): Promise<FetchSavedDesignResult> {
  let row: DesignRead
  try {
    row = await getDesign(designId)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return { ok: false, error: 'This design no longer exists.', reason: 'not-found' }
    }
    return {
      ok: false,
      error:
        err instanceof ApiError && err.status !== 0
          ? err.message
          : 'Could not reach FashionRise to open this design.',
      reason: 'network',
    }
  }
  const record = parseSavedDesign(row, ownerId)
  if (!record) {
    return {
      ok: false,
      error: 'This design cannot be opened because its saved data is not in a supported format.',
      reason: 'invalid',
    }
  }
  return { ok: true, record }
}

export type DeleteSavedDesignResult =
  | { ok: true; alreadyGone: boolean }
  | { ok: false; error: string; outcomeUncertain: boolean; canRetry: boolean }

const DELETE_OFFLINE_MESSAGE =
  'You are offline. The design was not deleted. Reconnect and try again.'

async function savedDesignStillPresent(ownerId: string, designId: string): Promise<boolean | null> {
  try {
    const mine = await listMyDesigns()
    return mine.some((row) => {
      const parsed = parseSavedDesign(row, ownerId)
      return parsed?.id === designId
    })
  } catch {
    try {
      await getDesign(designId)
      return true
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return false
      return null
    }
  }
}

/**
 * Permanently delete one owner-private saved design via the saved-only endpoint.
 * Offline requests are never sent. Ambiguous network/5xx responses are reconciled
 * against the owner's list (or GET) before success is claimed. A verified 404 is
 * treated as idempotent success (already deleted on another device).
 */
export async function deleteSavedDesign(
  ownerId: string,
  designId: string,
): Promise<DeleteSavedDesignResult> {
  if (isOffline()) {
    return { ok: false, error: DELETE_OFFLINE_MESSAGE, outcomeUncertain: false, canRetry: true }
  }

  try {
    await apiRequest<void>(`/designs/saved/${designId}`, { method: 'DELETE' })
    return { ok: true, alreadyGone: false }
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return { ok: true, alreadyGone: true }
    }

    const uncertain = outcomeUncertain(err)
    if (uncertain) {
      const present = await savedDesignStillPresent(ownerId, designId)
      if (present === false) {
        return { ok: true, alreadyGone: true }
      }
      if (present === true) {
        return {
          ok: false,
          error:
            err instanceof ApiError && err.status !== 0
              ? err.message
              : 'Could not reach FashionRise. The design was not deleted. Try again.',
          outcomeUncertain: false,
          canRetry: true,
        }
      }
      return {
        ok: false,
        error:
          'Could not confirm whether the design was deleted. Refresh My Designs before trying again.',
        outcomeUncertain: true,
        canRetry: true,
      }
    }

    return {
      ok: false,
      error:
        err instanceof ApiError && err.status !== 0
          ? err.message
          : 'Could not delete this design. Try again.',
      outcomeUncertain: false,
      canRetry: err instanceof ApiError ? err.status === 0 || err.status >= 500 : true,
    }
  }
}
