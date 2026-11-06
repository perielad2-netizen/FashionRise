import { afterEach, describe, expect, it } from 'vitest'
import { clearMagicJobId, persistMagicJobId, readMagicJobId } from '@/services/ai/magicJobStore'

describe('magicJobStore', () => {
  afterEach(() => {
    clearMagicJobId('user-a')
    clearMagicJobId('user-b')
  })

  it('persists per-user job ids for refresh recovery', () => {
    persistMagicJobId('user-a', 'job-111')
    persistMagicJobId('user-b', 'job-222')
    expect(readMagicJobId('user-a')).toBe('job-111')
    expect(readMagicJobId('user-b')).toBe('job-222')
  })

  it('does not share job ids across accounts', () => {
    persistMagicJobId('user-a', 'job-shared-check')
    expect(readMagicJobId('user-b')).toBeNull()
  })
})
