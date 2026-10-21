import { describe, expect, it } from 'vitest'
import { StrokeHistory, type ArtworkSnapshot } from '@/lib/history'
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

function art(strokes: Stroke[]): ArtworkSnapshot {
  return { strokes, fills: [] }
}

describe('studio stroke workflow', () => {
  it('records draw, undo, redo, and undoable clear', () => {
    const history = new StrokeHistory()
    let state = art([])

    const s1 = makeStroke()
    history.push(state)
    state = art([s1])

    const s2 = makeStroke()
    history.push(state)
    state = art([s1, s2])
    expect(state.strokes).toHaveLength(2)

    state = history.undo(state)!
    expect(state.strokes).toHaveLength(1)

    state = history.redo(state)!
    expect(state.strokes).toHaveLength(2)

    history.push(state)
    state = art([])
    state = history.undo(state)!
    expect(state.strokes).toHaveLength(2)
  })
})
