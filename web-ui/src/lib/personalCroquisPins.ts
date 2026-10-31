/**
 * Exact `(croquis_id, version)` pins for model=personal Studio underlays.
 * Regeneration never mutates older pins; erased croquis keep ink + pins,
 * underlay fails closed (no silent builtin remap).
 */

export type PersonalCroquisPin = {
  croquisId: string
  version: number
}

export function isPersonalCroquisPin(value: unknown): value is PersonalCroquisPin {
  if (!value || typeof value !== 'object') return false
  const v = value as { croquisId?: unknown; version?: unknown }
  return (
    typeof v.croquisId === 'string' &&
    v.croquisId.length > 0 &&
    typeof v.version === 'number' &&
    Number.isInteger(v.version) &&
    v.version > 0
  )
}

export function parsePersonalCroquisPinFields(raw: {
  personalCroquisId?: unknown
  personalCroquisVersion?: unknown
}): PersonalCroquisPin | null {
  const id = raw.personalCroquisId
  const version = raw.personalCroquisVersion
  if (id == null && version == null) return null
  if (typeof id !== 'string' || !id) return null
  if (typeof version !== 'number' || !Number.isInteger(version) || version < 1) return null
  return { croquisId: id, version }
}

export function personalPinFingerprint(pin: PersonalCroquisPin | null): string {
  if (!pin) return 'null'
  return `${pin.croquisId}@${pin.version}`
}

/** Geometry profile locked for Stage B fit-contain underlays. */
export const CROQUIS_GEOMETRY_PROFILE = 'fit_contain_768x1024_v1' as const
