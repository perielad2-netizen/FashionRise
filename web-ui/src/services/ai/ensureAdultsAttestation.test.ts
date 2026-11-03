import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/personalCroquisApi', () => ({
  attestAdults: vi.fn(async () => ({ id: 'a1', purpose: 'adults_beta' })),
}))

vi.mock('@/lib/personalCroquisNotices', () => ({
  approvedCroquisNoticeText: vi.fn((purpose: string) =>
    purpose === 'adults' ? 'Approved adults notice for try-on refresh.' : '',
  ),
  croquisNoticeVersion: vi.fn(() => 'adults-beta-2026-11-01'),
  sha256Hex: vi.fn(async () => 'abc123'),
}))

import { attestAdults } from '@/services/personalCroquisApi'
import {
  ADULTS_ATTESTATION_REQUIRED,
  ensureAdultsAttestationForTryOn,
  isAdultsAttestationError,
} from './ensureAdultsAttestation'

describe('ensureAdultsAttestationForTryOn (#180)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('records a fresh adults attestation from the approved notice', async () => {
    await ensureAdultsAttestationForTryOn()
    expect(attestAdults).toHaveBeenCalledWith(
      {
        adults_attested: true,
        notice_version: 'adults-beta-2026-11-01',
        notice_text_hash: 'abc123',
      },
      undefined,
    )
  })

  it('detects adults attestation API errors', () => {
    expect(
      isAdultsAttestationError('Adults-only beta attestation is required before Try On Person.'),
    ).toBe(true)
    expect(isAdultsAttestationError(ADULTS_ATTESTATION_REQUIRED)).toBe(true)
    expect(isAdultsAttestationError(SMART_TRY_ON_LIKE)).toBe(false)
  })
})

const SMART_TRY_ON_LIKE =
  'We could not create a try-on preview for this design. Your sketch is unchanged — you can edit and try again.'
