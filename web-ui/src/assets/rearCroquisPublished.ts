import type { SelectableBuiltinModelId } from '@/assets/modelLibrary'

/**
 * Explicit rear-croquis publish manifest. URLs may exist in the library map, but Back
 * Studio is gated until an id is set to `true` here (assets not shipped yet).
 */
export const REAR_CROQUIS_PUBLISHED: Readonly<Record<SelectableBuiltinModelId, boolean>> = {
  'female-straight': false,
  'female-hand-hip': false,
  'female-contrapposto': false,
  'female-cross-ankle': false,
  'female-atelier': false,
  'female-cross-leg': false,
  'male-straight': false,
  'male-step': false,
  'male-walk': false,
  'male-contrapposto': false,
}

export function isRearCroquisPublished(id: SelectableBuiltinModelId): boolean {
  return REAR_CROQUIS_PUBLISHED[id] === true
}
