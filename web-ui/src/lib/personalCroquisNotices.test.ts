import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, describe, expect, it, vi } from 'vitest'

describe('personalCroquisNotices fail-closed', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('uses static import.meta.env.VITE_* access only (#158 Vite replacement)', () => {
    const srcPath = path.join(path.dirname(fileURLToPath(import.meta.url)), 'personalCroquisNotices.ts')
    const src = readFileSync(srcPath, 'utf8')
    // Strip block + line comments so the #158 docstring mentioning dynamic access is ignored.
    const code = src
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/(^|[^:])\/\/.*$/gm, '$1')
    expect(code).toContain('import.meta.env.VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT')
    expect(code).toContain('import.meta.env.VITE_MY_CROQUIS_STORAGE_NOTICE_TEXT')
    expect(code).toContain('import.meta.env.VITE_MY_CROQUIS_AI_NOTICE_TEXT')
    expect(code).not.toMatch(/import\.meta\.env\s*\[/)
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
    vi.stubEnv('VITE_MY_CROQUIS_AI_NOTICE_TEXT', 'SYNTHETIC_TEST_AI_NOTICE_V1')
    const mod = await import('./personalCroquisNotices')
    expect(mod.approvedCroquisNoticeText('adults')).toBe('SYNTHETIC_TEST_ADULTS_NOTICE_V1')
    expect(mod.croquisNoticesAuthorized()).toBe(true)
  })

  it('requires AI notice for combined Upload & Generate authorization', async () => {
    vi.stubEnv('VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT', 'SYNTHETIC_TEST_ADULTS_NOTICE_V1')
    vi.stubEnv('VITE_MY_CROQUIS_STORAGE_NOTICE_TEXT', 'SYNTHETIC_TEST_STORAGE_NOTICE_V1')
    vi.stubEnv('VITE_MY_CROQUIS_AI_NOTICE_TEXT', '')
    const mod = await import('./personalCroquisNotices')
    expect(mod.croquisNoticesAuthorized()).toBe(false)
  })
})
