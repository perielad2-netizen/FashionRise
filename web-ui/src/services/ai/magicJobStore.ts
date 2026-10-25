const keyFor = (userId: string) => `fr.magic.lastJob.${userId}`
const opKeyFor = (userId: string) => `fr.magic.lastOperation.${userId}`

export type MagicOperationRecord = {
  operationId: string
  frontJobId?: string
  backJobId?: string
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
): MagicOperationRecord | null {
  const prev = readMagicOperation(userId)
  if (!prev) return null
  const next: MagicOperationRecord = {
    ...prev,
    updatedAt: new Date().toISOString(),
    ...(side === 'front' ? { frontJobId: jobId } : { backJobId: jobId }),
  }
  persistMagicOperation(userId, next)
  return next
}
