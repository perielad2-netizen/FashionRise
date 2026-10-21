const keyFor = (userId: string) => `fr.magic.lastJob.${userId}`

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
