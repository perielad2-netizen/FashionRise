import { afterEach, describe, expect, it, vi } from 'vitest'

describe('personalCroquisNotices fail-closed', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('rejects empty and draft/placeholder notice text', async () => {
    vi.stubEnv('VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT', '')
    vi.stubEnv('VITE_MY_CROQUIS_STORAGE_NOTICE_TEXT', 'DRAFT placeholder — not legal')
    const mod = await import('./personalCroquisNotices')
    expect(mod.approvedCroquisNoticeText('adults')).toBe('')
    expect(mod.approvedCroquisNoticeText('storage')).toBe('')
    expect(mod.croquisNoticesAuthorized()).toBe(false)
  })

  it('accepts synthetic approved fixtures when injected', async () => {
    vi.stubEnv('VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT', 'SYNTHETIC_TEST_ADULTS_NOTICE_V1')
    vi.stubEnv('VITE_MY_CROQUIS_STORAGE_NOTICE_TEXT', 'SYNTHETIC_TEST_STORAGE_NOTICE_V1')
    const mod = await import('./personalCroquisNotices')
    expect(mod.approvedCroquisNoticeText('adults')).toBe('SYNTHETIC_TEST_ADULTS_NOTICE_V1')
    expect(mod.croquisNoticesAuthorized()).toBe(true)
  })
})
