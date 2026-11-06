/**
 * Bounded Studio-derived design hints for Try On Person V2.
 * Evidence only — never invent garment details beyond fills/strokes present.
 */

import { getFabricPromptShort } from '@/lib/fabricPromptCache'
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

function parseHexColor(hex: string): { r: number; g: number; b: number } | null {
  const m = /^#?([0-9A-Fa-f]{6})$/.exec(hex.trim())
  if (!m) return null
  const n = Number.parseInt(m[1]!, 16)
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 }
}

/** Near-black outline ink — never promote as a garment fill color (#182). */
function isOutlineInk(hex: string): boolean {
  const c = parseHexColor(hex)
  if (!c) return false
  return (c.r + c.g + c.b) / 3 <= 40
}

/** Pale cream/ivory/peach fills that vanish on white flatten (#182 bridal). */
function isPaleFabric(hex: string): boolean {
  const c = parseHexColor(hex)
  if (!c) return false
  return (c.r + c.g + c.b) / 3 >= 185
}

/**
 * Detect a deep open / plunging neckline from fill contours (top-center notch).
 * Heuristic only — OpenAI still must read image 2 pixels.
 */
export function detectOpenNecklineFromFills(
  fills: FillOp[],
  designHeight = 1024,
  designWidth = 768,
): boolean {
  const upper = fills
    .map((f) => ({ fill: f, b: fillBounds(f) }))
    .filter((x): x is { fill: FillOp; b: InkBounds } => Boolean(x.b))
    .filter(({ b }) => b.minY < designHeight * 0.45 && b.maxY > designHeight * 0.12)
  if (upper.length === 0) return false
  // Contour has a deep dent near top-center: minY of points near center is much
  // lower than minY at left/right shoulders of the same fill.
  for (const { fill, b } of upper) {
    const c = fill.contour
    if (!c || c.length < 8) continue
    const midX = (b.minX + b.maxX) / 2
    const halfW = Math.max((b.maxX - b.minX) / 2, 1)
    let shoulderMinY = Infinity
    let centerMinY = Infinity
    for (let i = 0; i + 1 < c.length; i += 2) {
      const x = c[i]!
      const y = c[i + 1]!
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue
      const dx = Math.abs(x - midX) / halfW
      if (dx <= 0.22) centerMinY = Math.min(centerMinY, y)
      else if (dx >= 0.45 && dx <= 1.05) shoulderMinY = Math.min(shoulderMinY, y)
    }
    if (!Number.isFinite(centerMinY) || !Number.isFinite(shoulderMinY)) continue
    const plunge = centerMinY - shoulderMinY
    if (plunge >= designHeight * 0.04 && plunge >= (b.maxY - b.minY) * 0.08) {
      // Reject tiny top fills; require some width so sleeves/hats don't trip this.
      if (b.maxX - b.minX >= designWidth * 0.18) return true
    }
  }
  return false
}

/** Two sleeve masses in the upper outer thirds of the design plane (#182). */
export function detectBilateralSleevesFromFills(
  fills: FillOp[],
  designHeight = 1024,
  designWidth = 768,
): boolean {
  let left = false
  let right = false
  for (const fill of fills) {
    const b = fillBounds(fill)
    if (!b) continue
    const cy = (b.minY + b.maxY) / 2
    if (cy > designHeight * 0.55 || cy < designHeight * 0.08) continue
    if (b.minX <= designWidth * 0.22) left = true
    if (b.maxX >= designWidth * 0.78) right = true
  }
  return left && right
}

/**
 * Dark footwear ink near the feet / hem (#184).
 * Heuristic: dark stroke or any opaque solid/gradient fill whose bounds sit in
 * the lower ~22% of the plane (filled black/brown shoes, not only outline ink).
 */
export function detectFootwearInk(
  strokes: Stroke[],
  fills: FillOp[],
  designHeight = 1024,
): boolean {
  const footBand = designHeight * 0.78
  for (const stroke of strokes) {
    if (stroke.tool !== 'draw') continue
    if (!isOutlineInk(stroke.color || '')) continue
    const b = strokeBounds(stroke)
    if (!b) continue
    if (b.minY >= footBand && b.maxY > footBand) return true
  }
  for (const fill of fills) {
    const style = fill.style
    if (style.kind !== 'solid' && style.kind !== 'gradient') continue
    const hex = style.kind === 'solid' ? style.color : style.colors[0]
    if (!hex) continue
    const b = fillBounds(fill)
    if (!b) continue
    // Shoe-sized: sits in the foot band and is not a full-leg pant fill.
    const h = b.maxY - b.minY
    if (b.minY < footBand) continue
    if (b.maxY <= footBand) continue
    if (h > designHeight * 0.28) continue
    // Dark enough to read as footwear (black/brown/navy), not pale skin/highlight.
    const c = parseHexColor(hex)
    if (!c) continue
    if ((c.r + c.g + c.b) / 3 > 140) continue
    return true
  }
  return false
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

/** Fashion-safe rewrite so sheer/see-through fabric labels do not trip sexual moderation. */
export function sanitizeFabricHintText(raw: string): string {
  let text = raw.trim().replace(/\s+/g, ' ')
  if (!text) return text
  text = text
    .replace(/\bsee[\s-]*thr(?:ough|o+gh)\b/gi, 'fine-knit')
    .replace(/\bsheer\b/gi, 'fine-knit')
    .replace(/\btransparent\b/gi, 'fine-knit')
    .replace(/\bsee[\s-]*thru\b/gi, 'fine-knit')
  return text.replace(/\s+/g, ' ').trim()
}

function fabricLabelForFill(fill: FillOp): string {
  const style = fill.style
  if (style.kind === 'uploaded-fabric') {
    return (getFabricPromptShort(style.assetId) || '').toLowerCase()
  }
  if (style.kind === 'fabric') {
    const preset = FABRIC_PRESETS.find((p) => p.id === style.fabricId)
    return (preset?.label ?? style.fabricId).toLowerCase()
  }
  return ''
}

function looksLikeHosieryLabel(label: string): boolean {
  return /\b(stocking|stockings|hosiery|tights|pantyhose|sock|socks)\b/i.test(label)
}

function looksLikeGloveLabel(label: string): boolean {
  return /\b(glove|gloves|mitt|mittens)\b/i.test(label)
}

/** Leg-band fills (and stocking-labeled fabrics) — exclude from one-piece torso union. */
export function isLikelyHosieryFill(fill: FillOp, designHeight = 1024): boolean {
  const label = fabricLabelForFill(fill)
  if (looksLikeHosieryLabel(label)) return true
  // Geometry alone would mis-read solid pant legs as hosiery — require a fabric fill.
  if (fill.style.kind !== 'uploaded-fabric' && fill.style.kind !== 'fabric') return false
  const b = fillBounds(fill)
  if (!b) return false
  // Tall fill that starts at/under the hip and runs down the legs.
  if (b.minY < designHeight * 0.48) return false
  if (b.maxY < designHeight * 0.7) return false
  const span = b.maxY - b.minY
  return span >= designHeight * 0.18
}

/** Hand/forearm fills or glove-labeled fabrics. */
export function isLikelyGloveFill(fill: FillOp, designHeight = 1024): boolean {
  const label = fabricLabelForFill(fill)
  if (looksLikeGloveLabel(label)) return true
  if (fill.style.kind !== 'uploaded-fabric' && fill.style.kind !== 'fabric') return false
  const b = fillBounds(fill)
  if (!b) return false
  const cy = (b.minY + b.maxY) / 2
  const h = b.maxY - b.minY
  const w = b.maxX - b.minX
  if (cy < designHeight * 0.25 || cy > designHeight * 0.75) return false
  if (h > designHeight * 0.28 || w > designHeight * 0.22) return false
  // Peripheral on the canvas (hands), not center torso.
  const midX = (b.minX + b.maxX) / 2
  const edge = midX < designHeight * 0.28 || midX > designHeight * 0.72
  return edge
}

function apparelBodyFills(fills: FillOp[], designHeight = 1024): FillOp[] {
  return fills.filter(
    (f) => !isLikelyHosieryFill(f, designHeight) && !isLikelyGloveFill(f, designHeight),
  )
}

/**
 * Crop top + briefs (or similar) as two separate torso fills — not a continuous one-piece.
 */
export function detectSeparateTopBottom(
  fills: FillOp[],
  designHeight = 1024,
): boolean {
  const body = apparelBodyFills(fills, designHeight)
  const upper: InkBounds[] = []
  const lower: InkBounds[] = []
  for (const fill of body) {
    const b = fillBounds(fill)
    if (!b) continue
    const cy = (b.minY + b.maxY) / 2
    // Exclusive split — crop tops sit above mid torso; briefs/shorts/hips below.
    if (cy < designHeight * 0.47) upper.push(b)
    else lower.push(b)
  }
  if (upper.length < 1 || lower.length < 1) return false
  const top = unionBounds(upper)
  const bot = unionBounds(lower)
  if (!top || !bot) return false
  // Gap or only light overlap between crop hem and brief waist.
  return bot.minY + designHeight * 0.02 >= top.maxY - designHeight * 0.08
}

/**
 * Continuous torso→hip fill (one-piece swimsuit / bodysuit / dress) — not trousers
 * and not a waist-length top. Drives OpenAI hints so photo jeans are replaced.
 * Stockings/gloves and separate crop+brief sets are excluded.
 */
export function detectOnePieceFullCoverage(
  fills: FillOp[],
  designHeight = 1024,
): boolean {
  if (detectSeparateTopBottom(fills, designHeight)) return false
  const body = apparelBodyFills(fills, designHeight)
  const parts = body.map((f) => fillBounds(f)).filter(Boolean) as InkBounds[]
  const u = unionBounds(parts)
  if (!u) return false
  const span = u.maxY - u.minY
  if (span < designHeight * 0.28) return false
  if (u.maxY < designHeight * 0.5) return false
  if (u.minY > designHeight * 0.48) return false
  // Reject clear two-leg trousers — those use the trouser hint path instead.
  if (detectTrouserLegFills(body, designHeight).looksLikeTrousers) return false
  return true
}

/** Hem near the ankles / floor — gowns may keep photo shoes when no footwear is drawn. */
export function detectFloorLengthHem(fills: FillOp[], designHeight = 1024): boolean {
  const parts = fills.map((f) => fillBounds(f)).filter(Boolean) as InkBounds[]
  const u = unionBounds(parts)
  if (!u) return false
  return u.maxY >= designHeight * 0.85
}

/** High-cut one-piece hem (above ~mid-thigh) — must not be lengthened into a dress. */
export function detectHighCutOnePieceHem(fills: FillOp[], designHeight = 1024): boolean {
  if (!detectOnePieceFullCoverage(fills, designHeight)) return false
  const parts = fills.map((f) => fillBounds(f)).filter(Boolean) as InkBounds[]
  const u = unionBounds(parts)
  if (!u) return false
  return u.maxY < designHeight * 0.72
}

/** Build optional try-on design hints from the frozen front artwork. */
export function buildTryOnDesignHints(args: {
  strokes: Stroke[]
  fills?: FillOp[]
}): string[] {
  const fills = args.fills ?? []
  // #172 — geometry hints occupy the budget first so color/print hints cannot crowd them out.
  const priority: string[] = []
  const secondary: string[] = []
  const colors = new Set<string>()

  const hasHosiery = fills.some((f) => isLikelyHosieryFill(f))
  const hasGloves = fills.some((f) => isLikelyGloveFill(f))

  // #170 — additive trouser geometry hints only when Studio fills show two clear legs.
  const legs = detectTrouserLegFills(apparelBodyFills(fills))
  if (legs.looksLikeTrousers) {
    if (legs.looksLikeJumpsuit) {
      pushUnique(
        priority,
        'garment type: one-piece jumpsuit with trousers — not a dress, skirt, or swimsuit',
      )
    } else {
      pushUnique(priority, 'garment type: trousers / pant legs — not a dress or skirt')
    }
    pushUnique(priority, 'keep both leg openings separate; preserve each hem position from image 2')
    if (legs.looksLikeNarrow) {
      pushUnique(priority, 'preserve narrow leg width — do not flare, widen, or lengthen the legs')
    } else if (legs.looksLikeWide) {
      pushUnique(
        priority,
        'preserve the existing wide/flared leg width — do not narrow or merge the legs',
      )
    } else {
      pushUnique(priority, 'preserve original leg width and length — do not flare or merge legs')
    }
    pushUnique(priority, 'do not connect the legs into a continuous skirt panel')
  } else if (detectSeparateTopBottom(fills)) {
    pushUnique(
      priority,
      'garment type: separate top and bottom as drawn — keep both pieces; do not merge into one dress',
    )
    pushUnique(
      priority,
      'replace photo clothing on torso and hips with the drawn top and bottom; do not leave jeans under the design',
    )
  } else if (detectOnePieceFullCoverage(fills)) {
    // Continuous one-piece (swimsuit / bodysuit / dress) — do not leave photo jeans under it.
    // Two priority slots only so bridal neckline/sleeve/pale + color hints still fit.
    pushUnique(
      priority,
      'garment type: continuous one-piece covering torso through hips — not a separate top over trousers',
    )
    pushUnique(
      priority,
      "replace photo clothing wherever image 2's opaque garment covers; do not leave jeans, trousers, or shorts under this one-piece",
    )
    if (detectHighCutOnePieceHem(fills)) {
      // Owner back try-on lengthened high-cut one-piece into a knee dress.
      pushUnique(
        priority,
        'hem: high-cut one-piece as drawn — end at the designed leg openings; do not lengthen into a dress or skirt',
      )
    }
  }

  if (hasHosiery) {
    pushUnique(
      priority,
      'include drawn stockings/hosiery on both legs from image 2 — fine fashion knit; do not leave bare legs',
    )
  }
  if (hasGloves) {
    pushUnique(
      priority,
      'include drawn gloves on both hands from image 2 — do not leave bare hands when gloves are drawn',
    )
  }

  // #182 — open neckline + both sleeves before color noise (bridal / pale dresses).
  if (detectOpenNecklineFromFills(fills)) {
    pushUnique(
      priority,
      'neckline: deep open / plunging V as drawn — keep cleavage opening; do not fill or raise to a high neck',
    )
  }
  if (detectBilateralSleevesFromFills(fills)) {
    pushUnique(
      priority,
      'sleeves: both arms have sleeves in the artwork — keep both; do not invent one-shoulder or drop a sleeve',
    )
  }

  // #184 — dark footwear ink near the hem/feet must replace photo shoes/boots.
  // One-piece / high-cut with no drawn shoes → bare feet (do not keep photo boots).
  if (detectFootwearInk(args.strokes, fills)) {
    pushUnique(
      priority,
      'footwear: drawn shoes/boots in image 2 — replace the photo shoes/boots entirely; do not keep original boots',
    )
  } else if (detectOnePieceFullCoverage(fills) && !detectFloorLengthHem(fills)) {
    // Priority: photo boots were surviving when this was secondary-only.
    pushUnique(
      priority,
      'footwear: image 2 has no shoes drawn — remove photo boots/shoes; show bare feet matching image 1',
    )
  }

  let paleFillSeen = false
  for (const fill of fills) {
    const style = fill.style
    if (style.kind === 'solid') {
      const hex = style.color.toUpperCase()
      // Outline-ink solids are sketch scaffolding, not bridal fabric (#182).
      if (isOutlineInk(hex)) continue
      colors.add(hex)
      if (isPaleFabric(hex)) paleFillSeen = true
      pushUnique(secondary, `solid fill color ${hex}`)
    } else if (style.kind === 'gradient') {
      for (const c of style.colors) {
        const hex = c.toUpperCase()
        if (isOutlineInk(hex)) continue
        colors.add(hex)
        if (isPaleFabric(hex)) paleFillSeen = true
      }
      pushUnique(
        secondary,
        `gradient fill ${style.colors[0].toUpperCase()} to ${style.colors[1].toUpperCase()}`,
      )
    } else if (style.kind === 'fabric') {
      const preset = FABRIC_PRESETS.find((p) => p.id === style.fabricId)
      const label = sanitizeFabricHintText(preset?.label ?? style.fabricId)
      pushUnique(secondary, `${label} repeating fabric fill — keep exact Studio print geometry`)
    } else if (style.kind === 'uploaded-fabric') {
      const promptShort = sanitizeFabricHintText(getFabricPromptShort(style.assetId) || '')
      pushUnique(
        secondary,
        promptShort
          ? `${promptShort} repeating fill — preserve exact print topology from artwork pixels`
          : 'uploaded fabric repeating fill — preserve the exact print topology from the artwork pixels',
      )
    }
  }

  if (paleFillSeen) {
    pushUnique(
      priority,
      'intentional pale/cream/ivory/peach fabric — keep that light color opaque; it is not empty paper',
    )
  }

  // Stroke ink only if not already a fill color and not near-black outline.
  for (const stroke of args.strokes) {
    if (stroke.tool !== 'draw') continue
    if (typeof stroke.color === 'string' && stroke.color) {
      const hex = stroke.color.toUpperCase()
      if (isOutlineInk(hex)) continue
      colors.add(hex)
    }
  }

  if (colors.size > 0) {
    pushUnique(
      secondary,
      `exact designer colors: ${[...colors].slice(0, 6).join(', ')}`,
    )
  }

  if (hasUpperAccessoryInk(args.strokes)) {
    pushUnique(
      secondary,
      'upper-plane ink present — include any drawn hat/cap accessory from image 2',
    )
  }

  if (args.strokes.some((s) => s.tool === 'draw') || fills.length > 0) {
    pushUnique(
      secondary,
      'preserve print topology from image 2 pixels (checkerboard ≠ stripes)',
    )
  }

  const hints = [...priority]
  for (const h of secondary) {
    if (hints.length >= MAX_HINTS) break
    pushUnique(hints, h)
  }
  return hints.slice(0, MAX_HINTS)
}

/**
 * Shoe-sized fill sitting in the foot band (not a pant leg). Erasing shoes leaves
 * these FillOps in the document while capture alpha is punched out — including them
 * in the live Y span false-fails "lost lower parts".
 */
function isFootwearLikeFillBounds(b: InkBounds, designHeight: number): boolean {
  const footBand = designHeight * 0.78
  const h = b.maxY - b.minY
  if (b.minY < footBand) return false
  if (h > designHeight * 0.28) return false
  return true
}

/** Live ink vertical span for capture completeness checks (#170). */
export function liveArtworkYSpan(args: {
  strokes: Stroke[]
  fills?: FillOp[]
  /**
   * Try On completeness only: measure apparel body span, not erased shoe geometry.
   * Erasing shoes leaves draw strokes + shoe FillOps in the document while capture
   * alpha is punched out. Foot-band-only fills and strokes below the apparel hem
   * must not inflate live maxY (owner back croquis 2026-11-05).
   */
  forTryOnCompleteness?: boolean
  designHeight?: number
}): InkBounds | null {
  const fills = args.fills ?? []
  const designHeight = args.designHeight ?? 1024
  const fillParts = fills.map((f) => fillBounds(f))
  let strokeParts = args.strokes
    .filter((s) => s.tool === 'draw')
    .map((s) => strokeBounds(s))

  if (!args.forTryOnCompleteness) {
    return unionBounds([...strokeParts, ...fillParts])
  }

  // Apparel body fills only — drop shoe-sized foot-band fills that erase punched out.
  const apparelFillParts = fillParts.filter((b): b is InkBounds => {
    if (!b) return false
    return !isFootwearLikeFillBounds(b, designHeight)
  })
  const apparelUnion = unionBounds(apparelFillParts)
  if (!apparelUnion) {
    return unionBounds([...strokeParts, ...fillParts])
  }

  const hemPad = 24
  const apparelHem = apparelUnion.maxY
  // When the body hem ends above the feet, ignore anything entirely below it
  // (full shoe strokes, ankle crumbs, leftover shoe fills already dropped).
  if (apparelHem < designHeight * 0.78) {
    strokeParts = strokeParts.filter((b) => {
      if (!b) return false
      return b.minY <= apparelHem + hemPad
    })
    return unionBounds([...strokeParts, ...apparelFillParts])
  }

  return unionBounds([...strokeParts, ...apparelFillParts])
}
