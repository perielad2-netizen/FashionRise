import {
  backArtworkFromDoc,
  draftContentFingerprint,
  frontArtworkFromDoc,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import { FABRIC_PRESETS, type FillOp } from '@/lib/fills'
import { sampleColorFromStyle } from '@/lib/paintFills'

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

function fillMaterialColors(fill: FillOp): string[] {
  const style = fill.style
  // Applied solid/gradient pigment and built-in fabric presets.
  // Uploaded fabric has no client hex — never invent one.
  if (style.kind === 'solid') return [style.color]
  if (style.kind === 'gradient') return [...style.colors]
  if (style.kind === 'fabric') return [sampleColorFromStyle(style)]
  return []
}

function fillMaterialLabels(fill: FillOp): string[] {
  const style = fill.style
  if (style.kind === 'fabric') {
    const preset = FABRIC_PRESETS.find((p) => p.id === style.fabricId)
    const name = preset ? preset.label : style.fabricId
    // Emphasize repeating tile identity — Magic receives the exact swatch separately.
    return [`${name} repeating textile (exact Studio tile reference)`]
  }
  if (style.kind === 'uploaded-fabric') {
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
    `fingerprint=${fingerprint.slice(0, 64)}`,
  ].join('; ')
  // Keep designer notes when provided; always append enhancement intent for Front+Back.
  const notesParts = [
    ...(trimmedNotes ? [trimmedNotes] : []),
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
