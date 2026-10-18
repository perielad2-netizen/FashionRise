import { describe, expect, it } from 'vitest'
import { StrokeHistory } from '@/lib/history'
import { createStrokeId, type Stroke } from '@/lib/strokes'

function makeStroke(): Stroke {
  return {
    id: createStrokeId(),
    tool: 'draw',
    points: [10, 10, 0.5, 20, 24, 0.5, 30, 40, 0.5],
    color: '#1C1C1E',
    size: 5,
    opacity: 1,
  }
}

describe('studio stroke workflow', () => {
  it('records draw, undo, redo, and undoable clear', () => {
    const history = new StrokeHistory()
    let strokes: Stroke[] = []

    const s1 = makeStroke()
    history.push(strokes)
    strokes = [s1]

    const s2 = makeStroke()
    history.push(strokes)
    strokes = [s1, s2]
    expect(strokes).toHaveLength(2)

    strokes = history.undo(strokes)!
    expect(strokes).toHaveLength(1)

    strokes = history.redo(strokes)!
    expect(strokes).toHaveLength(2)

    history.push(strokes)
    strokes = []
    strokes = history.undo(strokes)!
    expect(strokes).toHaveLength(2)
  })
})
