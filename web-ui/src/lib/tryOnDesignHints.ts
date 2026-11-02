/**
 * Bounded Studio-derived design hints for Try On Person V2.
 * Evidence only — never invent garment details beyond fills/strokes present.
 */

import { FABRIC_PRESETS, type FillOp } from '@/lib/fills'
import type { Stroke } from '@/lib/strokes'

const MAX_HINTS = 8
const MAX_HINT_LEN = 120

function pushUnique(out: string[], hint: string): void {
  const text = hint.trim().replace(/\s+/g, ' ')
  if (!text || out.length >= MAX_HINTS) return
  const clipped = text.length > MAX_HINT_LEN ? text.slice(0, MAX_HINT_LEN) : text
  if (out.some((h) => h.toLowerCase() === clipped.toLowerCase())) return
  out.push(clipped)
}

function strokeBounds(stroke: Stroke): { minY: number; maxY: number; minX: number; maxX: number } | null {
  const pts = stroke.points
  if (!pts || pts.length < 6) return null
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  for (let i = 0; i + 1 < pts.length; i += 3) {
    const x = pts[i]!
    const y = pts[i + 1]!
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue
    minX = Math.min(minX, x)
    maxX = Math.max(maxX, x)
    minY = Math.min(minY, y)
    maxY = Math.max(maxY, y)
  }
  if (!Number.isFinite(minX)) return null
  return { minX, maxX, minY, maxY }
}

/**
 * Detect likely headwear ink in the upper design plane (hat/cap strokes).
 * Heuristic only — prompt still requires pixel fidelity from garment PNG.
 */
function hasUpperAccessoryInk(strokes: Stroke[], designHeight = 1024): boolean {
  const headBand = designHeight * 0.28
  let upperInk = 0
  for (const stroke of strokes) {
    if (stroke.tool !== 'draw') continue
    const b = strokeBounds(stroke)
    if (!b) continue
    if (b.maxY <= headBand && b.minY < headBand * 0.85) {
      upperInk += 1
    }
  }
  return upperInk >= 1
}

type InkBounds = { minX: number; maxX: number; minY: number; maxY: number }

function unionBounds(parts: Array<InkBounds | null>): InkBounds | null {
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  for (const b of parts) {
    if (!b) continue
    minX = Math.min(minX, b.minX)
    maxX = Math.max(maxX, b.maxX)
    minY = Math.min(minY, b.minY)
    maxY = Math.max(maxY, b.maxY)
  }
  if (!Number.isFinite(minX)) return null
  return { minX, maxX, minY, maxY }
}

function fillBounds(fill: FillOp): InkBounds | null {
  const c = fill.contour
  if (!c || c.length < 4) return null
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  for (let i = 0; i + 1 < c.length; i += 2) {
    const x = c[i]!
    const y = c[i + 1]!
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue
    minX = Math.min(minX, x)
    maxX = Math.max(maxX, x)
    minY = Math.min(minY, y)
    maxY = Math.max(maxY, y)
  }
  if (!Number.isFinite(minX)) return null
  return { minX, maxX, minY, maxY }
}

/**
 * Deterministic Studio geometry: two separate lower fills that look like trouser legs.
 * Avoids dresses/skirts (single wide lower fill) and swimsuits (high hem).
 */
export function detectTrouserLegFills(
  fills: FillOp[],
  designHeight = 1024,
): {
  looksLikeTrousers: boolean
  looksLikeNarrow: boolean
  looksLikeWide: boolean
  looksLikeJumpsuit: boolean
} {
  const lower: Array<{ fill: FillOp; b: InkBounds }> = []
  const upper: Array<{ fill: FillOp; b: InkBounds }> = []
  for (const fill of fills) {
    const b = fillBounds(fill)
    if (!b) continue
    const cy = (b.minY + b.maxY) / 2
    if (cy >= designHeight * 0.48) lower.push({ fill, b })
    if (cy <= designHeight * 0.55) upper.push({ fill, b })
  }
  // Need two distinct lower lobes with a gap and hems not high-cut.
  if (lower.length < 2) {
    return {
      looksLikeTrousers: false,
      looksLikeNarrow: false,
      looksLikeWide: false,
      looksLikeJumpsuit: false,
    }
  }
  const sorted = [...lower].sort((a, b) => a.b.minX - b.b.minX)
  let bestGap = -1
  let left = sorted[0]!
  let right = sorted[1]!
  for (let i = 0; i + 1 < sorted.length; i++) {
    const a = sorted[i]!
    const b = sorted[i + 1]!
    const gap = b.b.minX - a.b.maxX
    if (gap > bestGap) {
      bestGap = gap
      left = a
      right = b
    }
  }
  const hem = Math.max(left.b.maxY, right.b.maxY)
  const avgW = ((left.b.maxX - left.b.minX) + (right.b.maxX - right.b.minX)) / 2
  const span = Math.max(right.b.maxX - left.b.minX, 1)
  const gapOk = bestGap >= Math.max(8, designHeight * 0.02)
  const hemOk = hem >= designHeight * 0.62
  // Each lobe should be a pant leg, not half a skirt panel.
  const legLike = avgW <= Math.max(designHeight * 0.22, span * 0.45)
  // Reject dress/skirt: one very wide lower fill would not appear as two lobes here.
  const looksLikeTrousers = gapOk && hemOk && legLike && bestGap > 0
  const looksLikeNarrow = looksLikeTrousers && avgW <= designHeight * 0.12
  const looksLikeWide = looksLikeTrousers && avgW >= designHeight * 0.16
  const looksLikeJumpsuit = looksLikeTrousers && upper.length >= 1
  return { looksLikeTrousers, looksLikeNarrow, looksLikeWide, looksLikeJumpsuit }
}

/** Build optional try-on design hints from the frozen front artwork. */
export function buildTryOnDesignHints(args: {
  strokes: Stroke[]
  fills?: FillOp[]
}): string[] {
  const fills = args.fills ?? []
  const hints: string[] = []
  const colors = new Set<string>()

  for (const fill of fills) {
    const style = fill.style
    if (style.kind === 'solid') {
      colors.add(style.color.toUpperCase())
      pushUnique(hints, `solid fill color ${style.color.toUpperCase()}`)
    } else if (style.kind === 'gradient') {
      for (const c of style.colors) colors.add(c.toUpperCase())
      pushUnique(
        hints,
        `gradient fill ${style.colors[0].toUpperCase()} to ${style.colors[1].toUpperCase()}`,
      )
    } else if (style.kind === 'fabric') {
      const preset = FABRIC_PRESETS.find((p) => p.id === style.fabricId)
      const label = preset?.label ?? style.fabricId
      pushUnique(hints, `${label} repeating fabric fill — keep exact Studio print geometry`)
    } else if (style.kind === 'uploaded-fabric') {
      pushUnique(
        hints,
        'uploaded fabric repeating fill — preserve the exact print topology from the artwork pixels',
      )
    }
  }

  for (const stroke of args.strokes) {
    if (stroke.tool !== 'draw') continue
    if (typeof stroke.color === 'string' && stroke.color) {
      colors.add(stroke.color.toUpperCase())
    }
  }

  if (colors.size > 0) {
    pushUnique(
      hints,
      `exact designer colors: ${[...colors].slice(0, 6).join(', ')}`,
    )
  }

  if (hasUpperAccessoryInk(args.strokes)) {
    pushUnique(
      hints,
      'upper-plane ink present — include any drawn hat/cap accessory from image 2',
    )
  }

  if (args.strokes.some((s) => s.tool === 'draw') || fills.length > 0) {
    pushUnique(
      hints,
      'preserve print topology from image 2 pixels (checkerboard ≠ stripes)',
    )
  }

  // #170 — additive trouser geometry hints only when Studio fills show two clear legs.
  const legs = detectTrouserLegFills(fills)
  if (legs.looksLikeTrousers) {
    if (legs.looksLikeJumpsuit) {
      pushUnique(
        hints,
        'garment type: one-piece jumpsuit with trousers — not a dress, skirt, or swimsuit',
      )
    } else {
      pushUnique(hints, 'garment type: trousers / pant legs — not a dress or skirt')
    }
    pushUnique(hints, 'keep both leg openings separate; preserve each hem position from image 2')
    if (legs.looksLikeNarrow) {
      pushUnique(hints, 'preserve narrow leg width — do not flare, widen, or lengthen the legs')
    } else if (legs.looksLikeWide) {
      pushUnique(
        hints,
        'preserve the existing wide/flared leg width — do not narrow or merge the legs',
      )
    } else {
      pushUnique(hints, 'preserve original leg width and length — do not flare or merge legs')
    }
    pushUnique(hints, 'do not connect the legs into a continuous skirt panel')
  }

  return hints.slice(0, MAX_HINTS)
}

/** Live ink vertical span for capture completeness checks (#170). */
export function liveArtworkYSpan(args: {
  strokes: Stroke[]
  fills?: FillOp[]
}): InkBounds | null {
  const strokeParts = args.strokes
    .filter((s) => s.tool === 'draw')
    .map((s) => strokeBounds(s))
  const fillParts = (args.fills ?? []).map((f) => fillBounds(f))
  return unionBounds([...strokeParts, ...fillParts])
}
