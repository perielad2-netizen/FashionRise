/**
 * Create My Croquis geometry profile `fit_contain_768x1024_v1`.
 * Shared by Studio underlay paint and Stage B tests — no subject center-crop.
 */
import { DESIGN_HEIGHT, DESIGN_WIDTH } from '@/lib/strokes'

export const CROQUIS_GEOMETRY_PROFILE = 'fit_contain_768x1024_v1' as const

/** Fit-contain destination rect into the design plane (transparent letterbox/pillarbox). */
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
