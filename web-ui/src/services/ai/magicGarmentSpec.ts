import {
  backArtworkFromDoc,
  draftContentFingerprint,
  frontArtworkFromDoc,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import { getFabricPromptShort } from '@/lib/fabricPromptCache'
import { isGarmentScalePatternedFill } from '@/lib/fabricSwatchCapture'
import { FABRIC_PRESETS, type FillOp } from '@/lib/fills'
import { sampleColorFromStyle } from '@/lib/paintFills'
import {
  detectBilateralSleevesFromFills,
  detectOpenNecklineFromFills,
} from '@/lib/tryOnDesignHints'

type SideBag = { strokes: StudioDraftDocument['strokes']; fills: FillOp[] }

/**
 * Bounded garment context for dual Magic — keys must match backend
 * `_SHARED_GARMENT_SPEC_KEYS` (PR #70). No invented garment details.
 */
export type SharedGarmentSpec = {
  notes?: string
  colors?: string[]
  main_colors?: string[]
  materials?: string[]
  details?: string
  garment_category?: string
}

function parseHex(hex: string): { r: number; g: number; b: number } | null {
  const m = /^#?([0-9A-Fa-f]{6})$/.exec(hex.trim())
  if (!m) return null
  const n = Number.parseInt(m[1]!, 16)
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 }
}

/** Near-black outline ink is linework — never a bridal fill (#182/#183). */
function isOutlineInk(hex: string): boolean {
  const c = parseHex(hex)
  if (!c) return false
  return (c.r + c.g + c.b) / 3 <= 40
}

function isPaleFabric(hex: string): boolean {
  const c = parseHex(hex)
  if (!c) return false
  return (c.r + c.g + c.b) / 3 >= 185
}

function fillMaterialColors(fill: FillOp): string[] {
  const style = fill.style
  // Applied solid/gradient pigment and built-in fabric presets.
  // Uploaded fabric has no client hex — never invent one.
  // Skip outline-ink solids so #111111 does not become "main" bridal fabric.
  if (style.kind === 'solid') {
    return isOutlineInk(style.color) ? [] : [style.color]
  }
  if (style.kind === 'gradient') {
    return style.colors.filter((c) => !isOutlineInk(c))
  }
  // Tiny accessory fabric fills (shoes) must not set main garment color.
  if (style.kind === 'fabric') {
    if (!isGarmentScalePatternedFill(fill)) return []
    return [sampleColorFromStyle(style)]
  }
  return []
}

function fillMaterialLabels(fill: FillOp): string[] {
  const style = fill.style
  // Only garment-scale patterned fills become Magic "materials" — shoe satin
  // must not replace ink-painted dress colors in the garment spec.
  if (style.kind === 'fabric') {
    if (!isGarmentScalePatternedFill(fill)) return []
    const preset = FABRIC_PRESETS.find((p) => p.id === style.fabricId)
    const name = preset ? preset.label : style.fabricId
    // Emphasize repeating tile identity — Magic receives the exact swatch separately.
    return [`${name} repeating textile (exact Studio tile reference)`]
  }
  if (style.kind === 'uploaded-fabric') {
    if (!isGarmentScalePatternedFill(fill)) return []
    const promptShort = getFabricPromptShort(style.assetId)
    if (promptShort) {
      return [`${promptShort} repeating textile (exact Studio tile reference)`]
    }
    return ['uploaded fabric repeating textile (exact Studio tile reference)']
  }
  if (style.kind === 'gradient') return ['gradient fabric']
  return []
}

function collectFillColors(bag: SideBag, add: (c: string) => void): void {
  for (const f of bag.fills) {
    for (const c of fillMaterialColors(f)) add(c)
  }
}

function collectStrokeColors(bag: SideBag, add: (c: string) => void): void {
  for (const s of bag.strokes) add(s.color)
}

function collectMaterials(bag: SideBag, add: (m: string) => void): void {
  for (const f of bag.fills) {
    for (const m of fillMaterialLabels(f)) add(m)
  }
}

/**
 * Palette priority for Magic:
 * 1) Applied fill/gradient/built-in-fabric garment colors (main fabric)
 * 2) Drawn stroke/outline colors (linework only)
 * Never promote an unused selected brush swatch.
 */
export function paletteFromDoc(doc: StudioDraftDocument, max = 12): {
  colors: string[]
  main_colors: string[]
} {
  const fillSeen = new Set<string>()
  const strokeSeen = new Set<string>()
  const addFill = (c: string) => {
    const hex = c.toUpperCase()
    if (fillSeen.size < max) fillSeen.add(hex)
  }
  const addStroke = (c: string) => {
    const hex = c.toUpperCase()
    if (strokeSeen.size < max) strokeSeen.add(hex)
  }

  const front = frontArtworkFromDoc(doc)
  const back = backArtworkFromDoc(doc)
  collectFillColors(front, addFill)
  collectFillColors(back, addFill)
  collectStrokeColors(front, addStroke)
  collectStrokeColors(back, addStroke)

  const fillColors = [...fillSeen]
  const strokeColors = [...strokeSeen].filter((c) => !fillSeen.has(c))
  const colors = [...fillColors, ...strokeColors].slice(0, max)
  // main_colors = applied garment material when present; otherwise drawn stroke ink.
  const main_colors = (fillColors.length ? fillColors : strokeColors).slice(0, 4)
  return { colors, main_colors }
}

function materialsFromDoc(doc: StudioDraftDocument, max = 8): string[] {
  const seen = new Set<string>()
  const add = (m: string) => {
    const key = m.trim()
    if (!key || seen.size >= max) return
    seen.add(key)
  }
  collectMaterials(frontArtworkFromDoc(doc), add)
  collectMaterials(backArtworkFromDoc(doc), add)
  return [...seen]
}

/** Enhancement intent shared by Front-only and Dual Magic (both sides). */
const MAGIC_ENHANCEMENT_NOTES =
  'Polished professional fashion concept: keep silhouette/cut and Front/Back coherence; ' +
  'ONLY applied fill/gradient/fabric colors — invent no accent colors/panels/trims; ' +
  'normalize sketch glitches (uneven straps/sleeves, crooked edges, wobble); no traced/cartoon look.'

/** #183 — pale bridal / open neckline / both sleeves (same contract as Try On). */
function paleBridalNotes(front: SideBag, back: SideBag, mainColors: string[]): string[] {
  const notes: string[] = []
  const fills = [...front.fills, ...back.fills]
  const pale = mainColors.some((c) => isPaleFabric(c))
  if (pale) {
    notes.push(
      'intentional pale/cream/ivory/peach fabric — opaque garment, not empty paper or croquis body',
    )
  }
  if (detectOpenNecklineFromFills(fills) || detectOpenNecklineFromFills(front.fills)) {
    notes.push(
      'neckline: deep open / plunging V as drawn — keep cleavage opening; do not fill or raise to a high neck',
    )
  }
  if (
    detectBilateralSleevesFromFills(fills) ||
    detectBilateralSleevesFromFills(front.fills)
  ) {
    notes.push(
      'sleeves: both arms have sleeves as drawn — keep both; do not invent one-shoulder or drop a sleeve',
    )
  }
  return notes
}

/** Bounded garment context for dual Magic — no invented garment details. */
export function buildSharedGarmentSpec(
  doc: StudioDraftDocument,
  notes?: string,
): SharedGarmentSpec {
  const front = frontArtworkFromDoc(doc)
  const back = backArtworkFromDoc(doc)
  const trimmedNotes = notes?.trim()
  const { colors, main_colors } = paletteFromDoc(doc)
  const materials = materialsFromDoc(doc)
  const fingerprint = draftContentFingerprint(doc)
  const bridal = paleBridalNotes(front, back, main_colors)
  const details = [
    `model=${doc.model}`,
    `front_strokes=${front.strokes.length}`,
    `front_fills=${front.fills.length}`,
    `back_strokes=${back.strokes.length}`,
    `back_fills=${back.fills.length}`,
    'render=polished_professional_enhancement',
    'sketch_role=strong_guidance_not_pixel_trace',
    'color_authority=applied_fills_only',
    'sketch_cleanup=normalize_imperfections',
    ...(bridal.length ? ['pale_bridal_fidelity=1'] : []),
    `fingerprint=${fingerprint.slice(0, 64)}`,
  ].join('; ')
  // Keep designer notes when provided; always append enhancement intent for Front+Back.
  const notesParts = [
    ...(trimmedNotes ? [trimmedNotes] : []),
    ...bridal,
    MAGIC_ENHANCEMENT_NOTES,
  ]
  return {
    notes: notesParts.join(' ').slice(0, 500),
    ...(colors.length ? { colors, main_colors } : {}),
    ...(materials.length ? { materials } : {}),
    details: details.slice(0, 1000),
    garment_category: 'studio',
  }
}
