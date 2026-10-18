import { cloneStrokes, type Stroke } from '@/lib/strokes'

const DEFAULT_LIMIT = 80

export type HistorySnapshot = Stroke[]

/**
 * Bounded structured stroke history.
 * One completed gesture (or clear) = one undoable operation.
 */
export class StrokeHistory {
  private past: HistorySnapshot[] = []
  private future: HistorySnapshot[] = []
  private limit: number

  constructor(limit = DEFAULT_LIMIT) {
    this.limit = limit
  }

  push(current: Stroke[]): void {
    this.past.push(cloneStrokes(current))
    if (this.past.length > this.limit) {
      this.past.shift()
    }
    this.future = []
  }

  undo(current: Stroke[]): Stroke[] | null {
    if (this.past.length === 0) return null
    const previous = this.past.pop()!
    this.future.push(cloneStrokes(current))
    return previous
  }

  redo(current: Stroke[]): Stroke[] | null {
    if (this.future.length === 0) return null
    const next = this.future.pop()!
    this.past.push(cloneStrokes(current))
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
