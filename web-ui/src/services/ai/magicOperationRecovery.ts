import {
  fetchMagicOperationJobs,
  mapMagicOperationJobsBySide,
} from '@/services/ai/magicApi'
import {
  patchMagicOperationJob,
  persistMagicJobId,
  readMagicOperation,
  type MagicOperationRecord,
} from '@/services/ai/magicJobStore'

export type ResolvedDualMagicJobs = {
  operationId: string
  frontJobId: string
  backJobId: string
}

export type ResolveDualMagicJobsDeps = {
  readOperation?: (userId: string) => MagicOperationRecord | null
  fetchJobs?: typeof fetchMagicOperationJobs
  patchJob?: typeof patchMagicOperationJob
  persistJobId?: typeof persistMagicJobId
}

/**
 * Resolve Front/Back job ids for a dual Magic operation without enqueueing.
 *
 * Explicit recovery always refreshes via GET /ai/magic-operations/{id}/jobs —
 * even when Front/Back ids are already cached — so a newer failed-side retry is
 * selected. Cached ids alone must never be treated as authoritative current
 * attempts. On GET failure, do not return stale cached ids.
 */
export async function resolveDualMagicJobIds(
  userId: string,
  signal?: AbortSignal,
  deps: ResolveDualMagicJobsDeps = {},
): Promise<ResolvedDualMagicJobs | null> {
  const readOperation = deps.readOperation ?? readMagicOperation
  const fetchJobs = deps.fetchJobs ?? fetchMagicOperationJobs
  const patchJob = deps.patchJob ?? patchMagicOperationJob
  const persistJobId = deps.persistJobId ?? persistMagicJobId

  const stored = readOperation(userId)
  if (!stored?.operationId) return null

  // Always refresh from the server on recovery. Cached ids may predate a
  // failed-side retry created under the same operation (PR #70).
  let listed: Awaited<ReturnType<typeof fetchJobs>>
  try {
    listed = await fetchJobs(stored.operationId, signal)
  } catch (err) {
    // Fail closed: never present stale local Front/Back ids as current.
    throw err
  }

  const mapped = mapMagicOperationJobsBySide(listed.jobs ?? [])
  const frontJobId = mapped.frontJobId
  const backJobId = mapped.backJobId
  if (!frontJobId || !backJobId) return null

  patchJob(userId, 'front', frontJobId)
  patchJob(userId, 'back', backJobId)
  persistJobId(userId, frontJobId)
  return {
    operationId: stored.operationId,
    frontJobId,
    backJobId,
  }
}
