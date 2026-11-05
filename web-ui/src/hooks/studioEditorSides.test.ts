import { describe, expect, it, vi } from 'vitest'

vi.stubEnv('VITE_STUDIO_FRONT_BACK_ENABLED', 'true')
import { createEmptyDraftDocument } from '@/lib/draftDocument'
import {
  buildDocumentFromEditor,
  sideStateFromDocument,
  switchEditorSide,
  visibleInkFromState,
} from '@/hooks/studioEditorSides'

describe('studioEditorSides', () => {
  it('keeps inactive side ink when committing active-side edits', () => {
    const prev = createEmptyDraftDocument()
    const state = {
      activeSide: 'front' as const,
      frontStrokes: [
        {
          id: 'front',
          tool: 'draw',
          points: [0, 0, 1],
          color: '#1C1C1E',
          size: 2,
          opacity: 1,
        },
      ],
      frontFills: [],
      backStrokes: [
        {
          id: 'back',
          tool: 'draw',
          points: [1, 1, 1],
          color: '#1C1C1E',
          size: 2,
          opacity: 1,
        },
      ],
      backFills: [],
    }
    const next = buildDocumentFromEditor({
      prev,
      state,
      model: 'female-straight',
      customReferenceUrl: null,
      customReferenceKey: null,
      sizeId: 'thin',
      sizePx: 2,
      opacity: 1,
      color: '#1C1C1E',
      dimmed: false,
    })
    expect(next.back?.strokes).toHaveLength(1)
    expect(next.strokes).toHaveLength(1)
    const roundTrip = sideStateFromDocument(next)
    expect(roundTrip.backStrokes).toHaveLength(1)
    expect(roundTrip.frontStrokes).toHaveLength(1)
  })

  it('switchEditorSide only changes activeSide (no ink copy)', () => {
    const state = {
      activeSide: 'front' as const,
      frontStrokes: [
        {
          id: 'front-only',
          tool: 'draw',
          points: [0, 0, 1],
          color: '#1C1C1E',
          size: 2,
          opacity: 1,
        },
      ],
      frontFills: [],
      backStrokes: [
        {
          id: 'back-only',
          tool: 'draw',
          points: [1, 1, 1],
          color: '#1C1C1E',
          size: 2,
          opacity: 1,
        },
      ],
      backFills: [],
    }
    const onBack = switchEditorSide(state, 'back')
    expect(onBack.frontStrokes[0]?.id).toBe('front-only')
    expect(onBack.backStrokes[0]?.id).toBe('back-only')
    expect(visibleInkFromState(onBack).strokes[0]?.id).toBe('back-only')
  })
})
