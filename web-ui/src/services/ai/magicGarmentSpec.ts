import {
  backArtworkFromDoc,
  draftContentFingerprint,
  frontArtworkFromDoc,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import type { FillOp } from '@/lib/fills'

type SideBag = { strokes: StudioDraftDocument['strokes']; fills: FillOp[] }

/**
 * Bounded garment context for dual Magic — keys must match backend
 * `_SHARED_GARMENT_SPEC_KEYS` (PR #70). No invented garment details.
 */
export type SharedGarmentSpec = {
  notes?: string
  colors?: string[]
  main_colors?: string[]
  details?: string
  garment_category?: string
}

function fillMaterialColors(fill: FillOp): string[] {
  const style = fill.style
  // Applied solid/gradient pigment only. Uploaded fabric has no client hex — never invent one.
  if (style.kind === 'solid') return [style.color]
  if (style.kind === 'gradient') return [...style.colors]
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

/**
 * Palette priority for Magic:
 * 1) Applied fill/gradient garment colors (main fabric)
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

/** Bounded garment context for dual Magic — no invented garment details. */
export function buildSharedGarmentSpec(
  doc: StudioDraftDocument,
  notes?: string,
): SharedGarmentSpec {
  const front = frontArtworkFromDoc(doc)
  const back = backArtworkFromDoc(doc)
  const trimmedNotes = notes?.trim()
  const { colors, main_colors } = paletteFromDoc(doc)
  const fingerprint = draftContentFingerprint(doc)
  const details = [
    `model=${doc.model}`,
    `front_strokes=${front.strokes.length}`,
    `front_fills=${front.fills.length}`,
    `back_strokes=${back.strokes.length}`,
    `back_fills=${back.fills.length}`,
    `fingerprint=${fingerprint.slice(0, 64)}`,
  ].join('; ')
  return {
    ...(trimmedNotes ? { notes: trimmedNotes.slice(0, 500) } : {}),
    ...(colors.length ? { colors, main_colors } : {}),
    details: details.slice(0, 1000),
    garment_category: 'studio',
  }
}
