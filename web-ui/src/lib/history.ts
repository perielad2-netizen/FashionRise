import { cloneFills, type FillOp } from '@/lib/fills'
import { cloneStrokes, type Stroke } from '@/lib/strokes'

const DEFAULT_LIMIT = 80

export type ArtworkSnapshot = {
  strokes: Stroke[]
  fills: FillOp[]
}

/**
 * Bounded artwork history (ink + fills).
 * One completed gesture / fill / clear = one undoable operation.
 */
export class StrokeHistory {
  private past: ArtworkSnapshot[] = []
  private future: ArtworkSnapshot[] = []
  private limit: number

  constructor(limit = DEFAULT_LIMIT) {
    this.limit = limit
  }

  push(current: ArtworkSnapshot): void {
    this.past.push(cloneArtwork(current))
    if (this.past.length > this.limit) {
      this.past.shift()
    }
    this.future = []
  }

  undo(current: ArtworkSnapshot): ArtworkSnapshot | null {
    if (this.past.length === 0) return null
    const previous = this.past.pop()!
    this.future.push(cloneArtwork(current))
    return previous
  }

  redo(current: ArtworkSnapshot): ArtworkSnapshot | null {
    if (this.future.length === 0) return null
    const next = this.future.pop()!
    this.past.push(cloneArtwork(current))
    return next
  }

  canUndo(): boolean {
    return this.past.length > 0
  }

  canRedo(): boolean {
    return this.future.length > 0
  }

  clear(): void {
    this.past = []
    this.future = []
  }
}

export function cloneArtwork(state: ArtworkSnapshot): ArtworkSnapshot {
  return {
    strokes: cloneStrokes(state.strokes),
    fills: cloneFills(state.fills),
  }
}
