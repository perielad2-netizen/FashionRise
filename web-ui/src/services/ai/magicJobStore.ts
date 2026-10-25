import type { SharedGarmentSpec } from '@/services/ai/magicGarmentSpec'

const keyFor = (userId: string) => `fr.magic.lastJob.${userId}`
const opKeyFor = (userId: string) => `fr.magic.lastOperation.${userId}`

export type MagicOperationRecord = {
  operationId: string
  frontJobId?: string
  backJobId?: string
  /** Latest persisted idempotency key per side (initial or retry attempt). */
  frontIdempotencyKey?: string
  backIdempotencyKey?: string
  /** Immutable design identity bound at dual enqueue — required for retries. */
  designId?: string | null
  sourceRevision?: number
  contentFingerprint?: string
  referenceModelId?: string
  sharedGarmentSpec?: SharedGarmentSpec
  updatedAt: string
}

export function persistMagicJobId(userId: string, jobId: string): void {
  try {
    sessionStorage.setItem(keyFor(userId), jobId)
  } catch {
    // ignore quota / private mode
  }
}

export function readMagicJobId(userId: string): string | null {
  try {
    return sessionStorage.getItem(keyFor(userId))
  } catch {
    return null
  }
}

export function clearMagicJobId(userId: string): void {
  try {
    sessionStorage.removeItem(keyFor(userId))
  } catch {
    // ignore
  }
}

export function persistMagicOperation(userId: string, record: MagicOperationRecord): void {
  try {
    sessionStorage.setItem(opKeyFor(userId), JSON.stringify(record))
  } catch {
    // ignore
  }
}

export function readMagicOperation(userId: string): MagicOperationRecord | null {
  try {
    const raw = sessionStorage.getItem(opKeyFor(userId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as MagicOperationRecord
    if (!parsed || typeof parsed.operationId !== 'string') return null
    return parsed
  } catch {
    return null
  }
}

export function patchMagicOperationJob(
  userId: string,
  side: 'front' | 'back',
  jobId: string,
  idempotencyKey?: string,
): MagicOperationRecord | null {
  const prev = readMagicOperation(userId)
  if (!prev) return null
  const next: MagicOperationRecord = {
    ...prev,
    updatedAt: new Date().toISOString(),
    ...(side === 'front'
      ? {
          frontJobId: jobId,
          ...(idempotencyKey ? { frontIdempotencyKey: idempotencyKey } : {}),
        }
      : {
          backJobId: jobId,
          ...(idempotencyKey ? { backIdempotencyKey: idempotencyKey } : {}),
        }),
  }
  persistMagicOperation(userId, next)
  return next
}

/** Allocate a stable per-attempt retry key and persist it before POST. */
export function allocateMagicRetryIdempotencyKey(
  userId: string,
  side: 'front' | 'back',
): string | null {
  const prev = readMagicOperation(userId)
  if (!prev) return null
  const suffix =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID().slice(0, 8)
      : `${Date.now().toString(36)}`
  const key = `${prev.operationId}:${side}:retry:${suffix}`
  const next: MagicOperationRecord = {
    ...prev,
    updatedAt: new Date().toISOString(),
    ...(side === 'front' ? { frontIdempotencyKey: key } : { backIdempotencyKey: key }),
  }
  persistMagicOperation(userId, next)
  return key
}
