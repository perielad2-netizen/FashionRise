/**
 * Create My Croquis consent notice coordination with the backend.
 *
 * Production defaults are empty → fail closed (wizard cannot record consent).
 * Synthetic fixtures are for Vitest / offline harness only — never ship as
 * production-legal copy. Version strings must match backend settings.
 */

export const CROQUIS_ADULTS_NOTICE_VERSION = 'adults-beta-2026-10-30-draft'
export const CROQUIS_STORAGE_NOTICE_VERSION = 'storage-2026-10-30-draft'
export const CROQUIS_AI_NOTICE_VERSION = 'ai-provider-2026-10-30-draft'

/** Vitest / offline-only synthetic bodies (must match backend croquis_test_fixtures). */
export const SYNTHETIC_ADULTS_NOTICE = 'SYNTHETIC_TEST_ADULTS_NOTICE_V1'
export const SYNTHETIC_STORAGE_NOTICE = 'SYNTHETIC_TEST_STORAGE_NOTICE_V1'
export const SYNTHETIC_AI_NOTICE = 'SYNTHETIC_TEST_AI_NOTICE_V1'

export type CroquisNoticePurpose = 'adults' | 'storage' | 'ai'

function envNotice(name: string): string {
  const raw = (import.meta.env[name] as string | undefined) ?? ''
  return raw.trim()
}

/**
 * Approved notice text for a purpose. Empty → consent collection unauthorized.
 * Draft/placeholder markers are rejected the same as empty.
 */
export function approvedCroquisNoticeText(purpose: CroquisNoticePurpose): string {
  const text =
    purpose === 'adults'
      ? envNotice('VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT')
      : purpose === 'storage'
        ? envNotice('VITE_MY_CROQUIS_STORAGE_NOTICE_TEXT')
        : envNotice('VITE_MY_CROQUIS_AI_NOTICE_TEXT')
  if (!text) return ''
  const lower = text.toLowerCase()
  if (lower.includes('draft') || lower.includes('placeholder') || lower.includes('todo')) {
    return ''
  }
  return text
}

export function croquisNoticeVersion(purpose: CroquisNoticePurpose): string {
  if (purpose === 'adults') return CROQUIS_ADULTS_NOTICE_VERSION
  if (purpose === 'storage') return CROQUIS_STORAGE_NOTICE_VERSION
  return CROQUIS_AI_NOTICE_VERSION
}

export function croquisNoticesAuthorized(): boolean {
  return (
    Boolean(approvedCroquisNoticeText('adults')) &&
    Boolean(approvedCroquisNoticeText('storage'))
  )
}

export async function sha256Hex(text: string): Promise<string> {
  const data = new TextEncoder().encode(text)
  const digest = await crypto.subtle.digest('SHA-256', data)
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

/** Offline/test helper — inject synthetic notices into import.meta.env stubs via vitest. */
export const SYNTHETIC_NOTICE_ENV = {
  VITE_MY_CROQUIS_ADULTS_NOTICE_TEXT: SYNTHETIC_ADULTS_NOTICE,
  VITE_MY_CROQUIS_STORAGE_NOTICE_TEXT: SYNTHETIC_STORAGE_NOTICE,
  VITE_MY_CROQUIS_AI_NOTICE_TEXT: SYNTHETIC_AI_NOTICE,
} as const
