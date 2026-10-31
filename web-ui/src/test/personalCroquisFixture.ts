/**
 * Deterministic Stage B offline generated-croquis fixture (768×1024 PNG).
 * Used only in Vitest / local harnesses — never mounted as a production generate route.
 */

import { DESIGN_HEIGHT, DESIGN_WIDTH } from '@/lib/strokes'
import { CROQUIS_GEOMETRY_PROFILE } from '@/lib/personalCroquisPins'

export const STAGE_B_OFFLINE_CROQUIS_ID = '00000000-0000-4000-8000-0000000000b1'
export const STAGE_B_OFFLINE_CROQUIS_VERSION = 1
export const STAGE_B_GEOMETRY_PROFILE = CROQUIS_GEOMETRY_PROFILE

/** Tiny opaque PNG bytes for underlay tests (exact design plane size painted by callers). */
export function makeDeterministicCroquisPng(
  width = DESIGN_WIDTH,
  height = DESIGN_HEIGHT,
): Uint8Array {
  // Minimal valid 1×1 PNG then we rely on canvas fit-contain for plane tests.
  // For exact dimension tests, callers draw into an Offscreen/canvas at width×height.
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

/** Fit-contain destination rect for a source into the 768×1024 design plane (no crop). */
export function fitContainDestRect(
  srcW: number,
  srcH: number,
  boxW = DESIGN_WIDTH,
  boxH = DESIGN_HEIGHT,
): { x: number; y: number; w: number; h: number } {
  if (srcW <= 0 || srcH <= 0) return { x: 0, y: 0, w: boxW, h: boxH }
  const scale = Math.min(boxW / srcW, boxH / srcH)
  const w = srcW * scale
  const h = srcH * scale
  return {
    x: (boxW - w) / 2,
    y: (boxH - h) / 2,
    w,
    h,
  }
}
