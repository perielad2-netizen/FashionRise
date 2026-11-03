/**
 * #180 — Try On Person requires a fresh adults-beta attestation (24h window).
 * Refresh from the approved notice when the user affirmatively starts Try On.
 */
import { attestAdults } from '@/services/personalCroquisApi'
import {
  approvedCroquisNoticeText,
  croquisNoticeVersion,
  sha256Hex,
} from '@/lib/personalCroquisNotices'

export const ADULTS_ATTESTATION_REQUIRED =
  'Adults-only confirmation expired. Confirm the adults-only notice again, then retry Try On Person.'

export async function ensureAdultsAttestationForTryOn(signal?: AbortSignal): Promise<void> {
  const notice = approvedCroquisNoticeText('adults')
  if (!notice) {
    throw new Error(ADULTS_ATTESTATION_REQUIRED)
  }
  await attestAdults(
    {
      adults_attested: true,
      notice_version: croquisNoticeVersion('adults'),
      notice_text_hash: await sha256Hex(notice),
    },
    signal,
  )
}

export function isAdultsAttestationError(message: string | null | undefined): boolean {
  if (!message) return false
  return /adults-only|adults attestation|adults_beta|adults-beta/i.test(message)
}
