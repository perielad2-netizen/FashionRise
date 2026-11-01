/**
 * Contract fixtures mirror genuine Stage A serialized JSON (field names from
 * backend/app/schemas/personal_croquis.py). Do not invent FE-only aliases.
 */
import { describe, expect, it } from 'vitest'
import {
  acceptedVersionNumber,
  type PersonalCroquisRead,
  type PersonalCroquisVersionRead,
} from '@/services/personalCroquisApi'

/** Exact shape of Stage A PersonalCroquisRead JSON (strings for UUID/datetime). */
const STAGE_A_CROQUIS_WITH_ACCEPTED: PersonalCroquisRead = {
  id: '11111111-1111-4111-8111-111111111111',
  display_name: 'Studio pin subject',
  status: 'ready',
  source_asset_id: null,
  storage_consent_id: '22222222-2222-4222-8222-222222222222',
  adults_attestation_at: '2026-10-31T12:00:00+00:00',
  archived: false,
  erased: false,
  created_at: '2026-10-31T12:00:00+00:00',
  updated_at: '2026-10-31T12:05:00+00:00',
  latest_accepted_version: {
    version: 2,
    status: 'accepted',
    generated_asset_id: '33333333-3333-4333-8333-333333333333',
    geometry_profile: 'fit_contain_768x1024_v1',
    accepted_at: '2026-10-31T12:05:00+00:00',
  },
}

const STAGE_A_CROQUIS_NO_VERSION: PersonalCroquisRead = {
  ...STAGE_A_CROQUIS_WITH_ACCEPTED,
  id: '44444444-4444-4444-8444-444444444444',
  latest_accepted_version: null,
  source_asset_id: '55555555-5555-4555-8555-555555555555',
}

const STAGE_A_CROQUIS_ERASED: PersonalCroquisRead = {
  ...STAGE_A_CROQUIS_WITH_ACCEPTED,
  erased: true,
  archived: true,
}

const STAGE_A_VERSION_READ: PersonalCroquisVersionRead = {
  id: '66666666-6666-4666-8666-666666666666',
  croquis_id: STAGE_A_CROQUIS_WITH_ACCEPTED.id,
  version: 2,
  status: 'accepted',
  generated_asset_id: '33333333-3333-4333-8333-333333333333',
  geometry_profile: 'fit_contain_768x1024_v1',
  prompt_version: null,
  created_at: '2026-10-31T12:04:00+00:00',
  accepted_at: '2026-10-31T12:05:00+00:00',
}

describe('Stage A PersonalCroquisRead contract', () => {
  it('parses latest_accepted_version (not latest_accepted) for pinning', () => {
    const raw = JSON.parse(JSON.stringify(STAGE_A_CROQUIS_WITH_ACCEPTED)) as PersonalCroquisRead
    expect(raw).not.toHaveProperty('latest_accepted')
    expect(raw).not.toHaveProperty('archived_at')
    expect(raw).not.toHaveProperty('erase_requested_at')
    expect(acceptedVersionNumber(raw)).toBe(2)
    expect(raw.latest_accepted_version?.generated_asset_id).toBe(
      '33333333-3333-4333-8333-333333333333',
    )
    expect(raw.source_asset_id).toBeNull()
  })

  it('handles null source, no version, archived, and erased rows', () => {
    expect(acceptedVersionNumber(STAGE_A_CROQUIS_NO_VERSION)).toBeNull()
    expect(acceptedVersionNumber(STAGE_A_CROQUIS_ERASED)).toBeNull()
    expect(STAGE_A_CROQUIS_NO_VERSION.source_asset_id).toBeTruthy()
    expect(STAGE_A_CROQUIS_ERASED.archived).toBe(true)
  })

  it('version read exposes generated_asset_id for underlay resolve', () => {
    expect(STAGE_A_VERSION_READ.croquis_id).toBe(STAGE_A_CROQUIS_WITH_ACCEPTED.id)
    expect(STAGE_A_VERSION_READ.generated_asset_id).toBe(
      STAGE_A_CROQUIS_WITH_ACCEPTED.latest_accepted_version?.generated_asset_id,
    )
  })
})
