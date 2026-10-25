import { describe, expect, it, vi } from 'vitest'

vi.stubEnv('VITE_STUDIO_FRONT_BACK_ENABLED', 'true')
import { createEmptyDraftDocument } from '@/lib/draftDocument'
import { buildDocumentFromEditor, sideStateFromDocument } from '@/hooks/studioEditorSides'

describe('studioEditorSides', () => {
  it('keeps inactive side ink when committing active-side edits', () => {
    const prev = createEmptyDraftDocument()
    const state = {
      activeSide: 'front' as const,
      strokes: [
        {
          id: 'front',
          tool: 'draw',
          points: [0, 0, 1],
          color: '#1C1C1E',
          size: 2,
          opacity: 1,
        },
      ],
      fills: [],
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
    expect(roundTrip.strokes).toHaveLength(1)
  })
})
