import type { SelectableBuiltinModelId } from '@/assets/modelLibrary'

/**
 * Explicit rear-croquis publish manifest. URLs may exist in the library map, but Back
 * Studio is gated until an id is set to `true` here.
 *
 * Operator-approved PAIRS_09 (Issue #42): nine Front/Back pairs installed and aligned.
 * `female-atelier` has no approved Back — must stay false.
 *
 * Production feature flag `VITE_STUDIO_FRONT_BACK_ENABLED` remains OFF by default;
 * publishing here only unlocks Back when that flag is enabled in a test/local env.
 */
export const REAR_CROQUIS_PUBLISHED: Readonly<Record<SelectableBuiltinModelId, boolean>> = {
  'female-straight': true,
  'female-hand-hip': true,
  'female-contrapposto': true,
  'female-cross-ankle': true,
  'female-atelier': false,
  'female-cross-leg': true,
  'male-straight': true,
  'male-step': true,
  'male-walk': true,
  'male-contrapposto': true,
}

export function isRearCroquisPublished(id: SelectableBuiltinModelId): boolean {
  return REAR_CROQUIS_PUBLISHED[id] === true
}
