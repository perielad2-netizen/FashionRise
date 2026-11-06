import { describe, expect, it } from 'vitest'
import { StrokeHistory, type ArtworkSnapshot } from '@/lib/history'
import { createStrokeId, type Stroke } from '@/lib/strokes'

function stroke(n: number): Stroke {
  return {
    id: createStrokeId(),
    tool: 'draw',
    points: [0, 0, 0.5, n, n, 0.5],
    color: '#000',
    size: 4,
    opacity: 1,
  }
}

function art(strokes: Stroke[], fills: ArtworkSnapshot['fills'] = []): ArtworkSnapshot {
  return { strokes, fills }
}

describe('StrokeHistory', () => {
  it('undoes and redoes structured strokes and fills', () => {
    const history = new StrokeHistory()
    let current = art([])

    const a = stroke(1)
    history.push(current)
    current = art([a])
    expect(history.canUndo()).toBe(true)

    const b = stroke(2)
    history.push(current)
    current = art([a, b])

    const undone = history.undo(current)
    expect(undone?.strokes).toEqual([a])
    current = undone!

    const redone = history.redo(current)
    expect(redone?.strokes).toHaveLength(2)
  })

  it('makes clear undoable', () => {
    const history = new StrokeHistory()
    const a = stroke(1)
    let current = art([a])
    history.push(current)
    current = art([])
    const restored = history.undo(current)
    expect(restored?.strokes).toEqual([a])
  })

  it('undoes a fill without losing strokes', () => {
    const history = new StrokeHistory()
    const a = stroke(1)
    const fill = {
      id: 'f1',
      contour: [10, 10, 40, 10, 40, 40, 10, 40],
      style: { kind: 'solid' as const, color: '#B91C1C' },
      seedX: 20,
      seedY: 20,
    }
    let current = art([a])
    history.push(current)
    current = art([a], [fill])
    const undone = history.undo(current)
    expect(undone?.strokes).toEqual([a])
    expect(undone?.fills).toEqual([])
    const redone = history.redo(undone!)
    expect(redone?.fills).toHaveLength(1)
  })
})
