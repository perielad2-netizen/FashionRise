import { describe, expect, it } from 'vitest'
import { StrokeHistory } from '@/lib/history'
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

describe('StrokeHistory', () => {
  it('undoes and redoes structured strokes', () => {
    const history = new StrokeHistory()
    let current: Stroke[] = []

    const a = stroke(1)
    history.push(current)
    current = [a]
    expect(history.canUndo()).toBe(true)

    const b = stroke(2)
    history.push(current)
    current = [a, b]

    const undone = history.undo(current)
    expect(undone).toEqual([a])
    current = undone!

    const redone = history.redo(current)
    expect(redone).toHaveLength(2)
  })

  it('makes clear undoable', () => {
    const history = new StrokeHistory()
    const a = stroke(1)
    let current = [a]
    history.push(current)
    current = []
    const restored = history.undo(current)
    expect(restored).toEqual([a])
  })
})
