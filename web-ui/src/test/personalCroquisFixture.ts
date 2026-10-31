/**
 * Deterministic Stage B offline generated-croquis fixture (768×1024 PNG).
 * Used only in Vitest / local harnesses — never mounted as a production generate route.
 */

import { DESIGN_HEIGHT, DESIGN_WIDTH } from '@/lib/strokes'
import { CROQUIS_GEOMETRY_PROFILE, fitContainDestRect } from '@/lib/croquisGeometry'

export const STAGE_B_OFFLINE_CROQUIS_ID = '00000000-0000-4000-8000-0000000000b1'
export const STAGE_B_OFFLINE_CROQUIS_VERSION = 1
export const STAGE_B_GEOMETRY_PROFILE = CROQUIS_GEOMETRY_PROFILE
export { fitContainDestRect }

/** Tiny opaque PNG bytes for underlay tests — production paint uses fitContainDestRect. */
export function makeDeterministicCroquisPng(
  width = DESIGN_WIDTH,
  height = DESIGN_HEIGHT,
): Uint8Array {
  void width
  void height
  const png = Uint8Array.from(
    atob(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
    ),
    (c) => c.charCodeAt(0),
  )
  return png
}
