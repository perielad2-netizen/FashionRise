import { DESIGN_HEIGHT, DESIGN_WIDTH } from '@/lib/strokes'

/** Absolute scale: CSS pixels per design-space pixel. 1 = 100%. */
export type ViewportState = {
  scale: number
  panX: number
  panY: number
}

export type ViewportSize = {
  width: number
  height: number
}

/** Relative zoom range vs Fit Page (Fit Width / 100% always remain attainable). */
export const ZOOM_REL_MIN = 0.5
export const ZOOM_REL_MAX = 6

export function fitPageScale(viewport: ViewportSize): number {
  const w = Math.max(1, viewport.width)
  const h = Math.max(1, viewport.height)
  return Math.min(w / DESIGN_WIDTH, h / DESIGN_HEIGHT)
}

export function fitWidthScale(viewport: ViewportSize): number {
  return Math.max(1, viewport.width) / DESIGN_WIDTH
}

/** Absolute 100%: one design pixel maps to one CSS pixel. */
export function absoluteHundredPercentScale(): number {
  return 1
}

export function scaleLimits(viewport: ViewportSize): { min: number; max: number } {
  const fit = fitPageScale(viewport)
  const width = fitWidthScale(viewport)
  const min = Math.max(0.05, Math.min(fit * ZOOM_REL_MIN, fit))
  const max = Math.max(fit * ZOOM_REL_MAX, width, 1, fit)
  return { min, max }
}

export function clampScale(scale: number, viewport: ViewportSize): number {
  if (!Number.isFinite(scale) || scale <= 0) return fitPageScale(viewport)
  const { min, max } = scaleLimits(viewport)
  return Math.min(max, Math.max(min, scale))
}

/** Center the design page in the viewport at the given scale. */
export function centerPan(scale: number, viewport: ViewportSize): ViewportState {
  const s = clampScale(scale, viewport)
  return {
    scale: s,
    panX: (viewport.width - DESIGN_WIDTH * s) / 2,
    panY: (viewport.height - DESIGN_HEIGHT * s) / 2,
  }
}

export function fitPage(viewport: ViewportSize): ViewportState {
  return centerPan(fitPageScale(viewport), viewport)
}

export function fitWidth(viewport: ViewportSize): ViewportState {
  const s = fitWidthScale(viewport)
  // Prefer top-aligned when taller than viewport so the neckline is reachable first.
  const contentH = DESIGN_HEIGHT * s
  const panY = contentH <= viewport.height ? (viewport.height - contentH) / 2 : 0
  return {
    scale: s,
    panX: (viewport.width - DESIGN_WIDTH * s) / 2,
    panY,
  }
}

export function hundredPercent(viewport: ViewportSize): ViewportState {
  return centerPan(absoluteHundredPercentScale(), viewport)
}

/**
 * Clamp pan so the design remains reachable — never pan completely out of view.
 * When the page is smaller than the viewport, allow any pan that keeps the full
 * page visible (not only dead-center) so zoom-around-pointer stays stable.
 */
export function clampPan(state: ViewportState, viewport: ViewportSize): ViewportState {
  const scale = clampScale(state.scale, viewport)
  const contentW = DESIGN_WIDTH * scale
  const contentH = DESIGN_HEIGHT * scale
  const margin = Math.min(48, viewport.width * 0.2, viewport.height * 0.2)

  let minX: number
  let maxX: number
  if (contentW <= viewport.width) {
    minX = 0
    maxX = viewport.width - contentW
  } else {
    minX = viewport.width - contentW - margin
    maxX = margin
  }

  let minY: number
  let maxY: number
  if (contentH <= viewport.height) {
    minY = 0
    maxY = viewport.height - contentH
  } else {
    minY = viewport.height - contentH - margin
    maxY = margin
  }

  const panX = Number.isFinite(state.panX) ? Math.min(maxX, Math.max(minX, state.panX)) : (minX + maxX) / 2
  const panY = Number.isFinite(state.panY) ? Math.min(maxY, Math.max(minY, state.panY)) : (minY + maxY) / 2
  return { scale, panX, panY }
}

export function screenToDesign(
  screenX: number,
  screenY: number,
  state: ViewportState,
): { x: number; y: number } {
  const scale = state.scale || 1
  return {
    x: (screenX - state.panX) / scale,
    y: (screenY - state.panY) / scale,
  }
}

export function designToScreen(
  designX: number,
  designY: number,
  state: ViewportState,
): { x: number; y: number } {
  return {
    x: designX * state.scale + state.panX,
    y: designY * state.scale + state.panY,
  }
}

/** Zoom around an anchor in screen/CSS space (pointer or pinch center). */
export function zoomAt(
  state: ViewportState,
  viewport: ViewportSize,
  nextScale: number,
  anchorScreenX: number,
  anchorScreenY: number,
): ViewportState {
  const design = screenToDesign(anchorScreenX, anchorScreenY, state)
  const scale = clampScale(nextScale, viewport)
  const panX = anchorScreenX - design.x * scale
  const panY = anchorScreenY - design.y * scale
  return clampPan({ scale, panX, panY }, viewport)
}

/**
 * Combined pinch (scale) + two-finger pan in one step.
 *
 * The design point under the *previous* gesture midpoint must map to the
 * *new* midpoint after the step. Using zoomAt(newMid) then panBy(delta) is
 * incorrect when distance and midpoint both change in the same frame.
 */
export function pinchPan(
  state: ViewportState,
  viewport: ViewportSize,
  nextScale: number,
  prevMidX: number,
  prevMidY: number,
  nextMidX: number,
  nextMidY: number,
): ViewportState {
  const design = screenToDesign(prevMidX, prevMidY, state)
  const scale = clampScale(nextScale, viewport)
  const panX = nextMidX - design.x * scale
  const panY = nextMidY - design.y * scale
  return clampPan({ scale, panX, panY }, viewport)
}

export function panBy(state: ViewportState, viewport: ViewportSize, dx: number, dy: number): ViewportState {
  return clampPan({ scale: state.scale, panX: state.panX + dx, panY: state.panY + dy }, viewport)
}

export function zoomPercent(scale: number): number {
  if (!Number.isFinite(scale) || scale <= 0) return 100
  return Math.round(scale * 100)
}

/** Pinch: scale factor from previous and current finger distances. */
export function pinchScaleFactor(
  prevDist: number,
  nextDist: number,
): number {
  if (!Number.isFinite(prevDist) || !Number.isFinite(nextDist) || prevDist <= 0 || nextDist <= 0) {
    return 1
  }
  return nextDist / prevDist
}

export function distance(a: { x: number; y: number }, b: { x: number; y: number }): number {
  return Math.hypot(b.x - a.x, b.y - a.y)
}

export function midpoint(
  a: { x: number; y: number },
  b: { x: number; y: number },
): { x: number; y: number } {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
}

export function isValidViewportSize(viewport: ViewportSize): boolean {
  return (
    Number.isFinite(viewport.width) &&
    Number.isFinite(viewport.height) &&
    viewport.width > 0 &&
    viewport.height > 0
  )
}

export function safeViewport(viewport: ViewportSize): ViewportSize {
  if (!isValidViewportSize(viewport)) return { width: DESIGN_WIDTH, height: DESIGN_HEIGHT }
  return {
    width: Math.max(1, viewport.width),
    height: Math.max(1, viewport.height),
  }
}
