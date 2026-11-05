import { cloneFills, type FillOp } from '@/lib/fills'
import { cloneStrokes, type Stroke } from '@/lib/strokes'

export type StudioPaperSide = 'front' | 'back'

export type StudioSideBag = {
  strokes: Stroke[]
  fills: FillOp[]
}

export function emptySideBag(): StudioSideBag {
  return { strokes: [], fills: [] }
}

export function cloneSideBag(bag: StudioSideBag): StudioSideBag {
  return { strokes: cloneStrokes(bag.strokes), fills: cloneFills(bag.fills) }
}

export function sideHasInk(bag: StudioSideBag): boolean {
  return bag.strokes.length > 0 || bag.fills.length > 0
}

/**
 * Structural gate for a present Back bag.
 *
 * - `null` / non-object → invalid (caller decides whether absence was allowed)
 * - `strokes` must be an array
 * - `fills`, when present, must be an array — never coerce a wrong type to `[]`
 * - omitted `fills` normalizes to `[]` (empty bag is valid)
 *
 * Does **not** validate stroke/fill item shapes; parsers do that atomically.
 */
export function normalizeSideBag(raw: unknown): StudioSideBag | null {
  if (!raw || typeof raw !== 'object') return null
  const bag = raw as { strokes?: unknown; fills?: unknown }
  if (!Array.isArray(bag.strokes)) return null
  if (bag.fills !== undefined && !Array.isArray(bag.fills)) return null
  return {
    strokes: bag.strokes as Stroke[],
    fills: Array.isArray(bag.fills) ? (bag.fills as FillOp[]) : [],
  }
}
