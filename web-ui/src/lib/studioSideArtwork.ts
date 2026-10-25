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

export function normalizeSideBag(raw: unknown): StudioSideBag | null {
  if (!raw || typeof raw !== 'object') return null
  const bag = raw as { strokes?: unknown; fills?: unknown }
  if (!Array.isArray(bag.strokes)) return null
  return { strokes: bag.strokes as Stroke[], fills: Array.isArray(bag.fills) ? (bag.fills as FillOp[]) : [] }
}
