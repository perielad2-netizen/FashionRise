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

function fillMaterialColors(fill: FillOp, opts: { forMain: boolean }): string[] {
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
  // Accessory fabric (shoes) belongs in the full palette so Magic sees satin,
  // but must not become main_colors (that would recolor the dress).
  if (style.kind === 'fabric') {
    if (opts.forMain && !isGarmentScalePatternedFill(fill)) return []
    return [sampleColorFromStyle(style)]
  }
  return []
}

function patternedFillName(fill: FillOp): string | null {
  const style = fill.style
  if (style.kind === 'fabric') {
    const preset = FABRIC_PRESETS.find((p) => p.id === style.fabricId)
    return preset ? preset.label : style.fabricId
  }
  if (style.kind === 'uploaded-fabric') {
    return getFabricPromptShort(style.assetId) || 'uploaded fabric'
  }
  return null
}

function fillMaterialLabels(fill: FillOp): string[] {
  const style = fill.style
  // Garment-scale patterned fills = primary textile (Image 2 when present).
  // Accessory-scale fills (shoes) stay in materials with an explicit accessory
  // label so Magic keeps satin shoes without spreading that textile on the dress.
  if (style.kind === 'fabric' || style.kind === 'uploaded-fabric') {
    const name = patternedFillName(fill)
    if (!name) return []
    if (isGarmentScalePatternedFill(fill)) {
      return [`${name} repeating textile (exact Studio tile reference)`]
    }
    return [
      `accessory textile: ${name} as painted in sketch Image 1 on shoes/trims — keep this fabric; do not recolor from dress ink outlines`,
    ]
  }
  if (style.kind === 'gradient') return ['gradient fabric']
  return []
}

function collectFillColors(
  bag: SideBag,
  add: (c: string) => void,
  opts: { forMain: boolean },
): void {
  for (const f of bag.fills) {
    for (const c of fillMaterialColors(f, opts)) add(c)
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
 * Accessory fabric colors appear in `colors` but not `main_colors`.
 * Never promote an unused selected brush swatch.
 */
export function paletteFromDoc(doc: StudioDraftDocument, max = 12): {
  colors: string[]
  main_colors: string[]
} {
  const allFillSeen = new Set<string>()
  const mainFillSeen = new Set<string>()
  const strokeSeen = new Set<string>()
  const addAllFill = (c: string) => {
    const hex = c.toUpperCase()
    if (allFillSeen.size < max) allFillSeen.add(hex)
  }
  const addMainFill = (c: string) => {
    const hex = c.toUpperCase()
    if (mainFillSeen.size < max) mainFillSeen.add(hex)
  }
  const addStroke = (c: string) => {
    const hex = c.toUpperCase()
    if (strokeSeen.size < max) strokeSeen.add(hex)
  }

  const front = frontArtworkFromDoc(doc)
  const back = backArtworkFromDoc(doc)
  collectFillColors(front, addAllFill, { forMain: false })
  collectFillColors(back, addAllFill, { forMain: false })
  collectFillColors(front, addMainFill, { forMain: true })
  collectFillColors(back, addMainFill, { forMain: true })
  collectStrokeColors(front, addStroke)
  collectStrokeColors(back, addStroke)

  const allFillColors = [...allFillSeen]
  const mainFillColors = [...mainFillSeen]
  const strokeColors = [...strokeSeen].filter((c) => !allFillSeen.has(c))
  const colors = [...allFillColors, ...strokeColors].slice(0, max)
  // main_colors = garment-scale fills/solids; else drawn stroke ink (not shoe satin).
  const main_colors = (mainFillColors.length ? mainFillColors : strokeColors).slice(0, 4)
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

/** Enhancement intent shared by Front-only and Dual Magic (both sides).
 * Glitch-erase verbs lead so shared-spec compact still keeps them when notes clip. */
const MAGIC_ENHANCEMENT_NOTES =
  'MUST erase sketch glitches (incomplete fills, leftover gaps, uneven lines, missing fabric, ' +
  'unfinished hands/legs/shoes) — restore matching fabric; do NOT treat unfilled gaps as cut-outs; ' +
  'WOW elevate rough/kid-like sketch into a stunning professional fashion illustration; ' +
  'keep the DESIGN IDEA (silhouette/cut, fabric/color theme, Front/Back coherence); ' +
  'ONLY applied fill/gradient/fabric colors — invent no accent colors/panels/trims; ' +
  'only keep clearly designed swim/lingerie/true-crop openings; no traced/cartoon look.'

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
    'color_authority=applied_fills_and_ink_combination',
    'accessory_fabric_fills=preserve_as_painted_in_sketch',
    'sketch_cleanup=smart_normalize_accidental_gaps',
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
