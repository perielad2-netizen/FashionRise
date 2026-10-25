import {
  backArtworkFromDoc,
  draftContentFingerprint,
  frontArtworkFromDoc,
  type StudioDraftDocument,
} from '@/lib/draftDocument'
import type { FillOp } from '@/lib/fills'

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

function fillColors(fill: FillOp): string[] {
  const style = fill.style
  if (style.kind === 'solid') return [style.color]
  if (style.kind === 'gradient') return [...style.colors]
  return []
}

function paletteFromDoc(doc: StudioDraftDocument, max = 12): string[] {
  const seen = new Set<string>()
  const add = (c: string) => {
    const hex = c.toUpperCase()
    if (seen.size < max) seen.add(hex)
  }
  add(doc.brush.color)
  for (const s of doc.strokes) add(s.color)
  for (const f of doc.fills ?? []) {
    for (const c of fillColors(f)) add(c)
  }
  const back = backArtworkFromDoc(doc)
  for (const s of back.strokes) add(s.color)
  for (const f of back.fills) {
    for (const c of fillColors(f)) add(c)
  }
  return [...seen]
}

/** Bounded garment context for dual Magic — no invented garment details. */
export function buildSharedGarmentSpec(
  doc: StudioDraftDocument,
  notes?: string,
): SharedGarmentSpec {
  const front = frontArtworkFromDoc(doc)
  const back = backArtworkFromDoc(doc)
  const trimmedNotes = notes?.trim()
  const colors = paletteFromDoc(doc)
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
    ...(colors.length ? { colors, main_colors: colors.slice(0, 4) } : {}),
    details: details.slice(0, 1000),
    garment_category: 'studio',
  }
}
