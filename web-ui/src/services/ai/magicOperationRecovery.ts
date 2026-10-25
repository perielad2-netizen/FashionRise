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
 * Prefer locally persisted ids. When the dual POST committed but the HTTP
 * response was lost (operationId/keys present, job ids missing), look up
 * existing jobs via GET /ai/magic-operations/{id}/jobs and patch the store.
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

  let frontJobId = stored.frontJobId ?? null
  let backJobId = stored.backJobId ?? null

  if (!frontJobId || !backJobId) {
    const listed = await fetchJobs(stored.operationId, signal)
    const mapped = mapMagicOperationJobsBySide(listed.jobs ?? [])
    frontJobId = frontJobId ?? mapped.frontJobId
    backJobId = backJobId ?? mapped.backJobId
    if (frontJobId) patchJob(userId, 'front', frontJobId)
    if (backJobId) patchJob(userId, 'back', backJobId)
  }

  if (!frontJobId || !backJobId) return null

  persistJobId(userId, frontJobId)
  return {
    operationId: stored.operationId,
    frontJobId,
    backJobId,
  }
}
