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

  return hints.slice(0, MAX_HINTS)
}
